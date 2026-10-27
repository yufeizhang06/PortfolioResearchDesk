"""Global-date walk-forward and interval purging, including nested TimeSeriesSplit."""

from dataclasses import dataclass
from datetime import datetime

from portfolio_research_desk.errors import DataError
from portfolio_research_desk.ml_config import MLConfig
from portfolio_research_desk.ml_data import Sample


def evaluation_boundary(decision_at: datetime) -> datetime:
    """Synthetic UTC session day start; no evaluation-day labels influence fitting."""
    return decision_at.replace(hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class Fold:
    fold_id: str
    stage: str
    train: tuple[int, ...]
    test: tuple[int, ...]
    purged: tuple[int, ...]
    buffered: tuple[int, ...]
    fit_at: datetime


def validate_fold(samples: tuple[Sample, ...], fold: Fold) -> None:
    indices = (*fold.train, *fold.test)
    if (
        not fold.train
        or not fold.test
        or len(set(indices)) != len(indices)
        or any(type(i) is not int or not 0 <= i < len(samples) for i in indices)
    ):
        raise DataError("Invalid or overlapping fold indices.")
    train, test = [samples[i] for i in fold.train], [samples[i] for i in fold.test]
    first = min(s.feature.decision_at for s in test)
    boundary = evaluation_boundary(first)
    if fold.fit_at != first or max(s.feature.decision_at for s in train) >= first:
        raise DataError("Fold violates global-date chronology or fit time.")
    for sample in (*train, *test):
        sample.feature.__post_init__()
        sample.__post_init__()
    if any(
        s.label is None or s.label.end_at >= boundary or s.label.known_at >= boundary for s in train
    ):
        raise DataError("Fold training contains overlapping or unknown labels.")


def validate_samples(samples: tuple[Sample, ...]) -> tuple[datetime, ...]:
    if not samples:
        raise DataError("Empty ML sample.")
    keys = [(s.feature.decision_at, s.feature.asset) for s in samples]
    if keys != sorted(set(keys)):
        raise DataError("ML rows must have unique ordered date/asset identities.")
    dates = tuple(sorted({s.feature.decision_at for s in samples}))
    assets = {s.feature.asset for s in samples}
    if len(samples) != len(assets) * len(dates):
        raise DataError("ML requires a complete fixed synthetic feature panel.")
    for sample in samples:
        sample.feature.__post_init__()
        sample.__post_init__()
        if sample.label:
            sample.label.__post_init__()
    return dates


def purged_fold(
    samples: tuple[Sample, ...],
    train_dates: tuple[datetime, ...],
    test_dates: tuple[datetime, ...],
    config: MLConfig,
    fold_id: str,
    stage: str = "development",
) -> Fold:
    """Drop whole dates if any label overlaps/is unknown; never add post-test training."""
    if not train_dates or not test_dates or max(train_dates) >= min(test_dates):
        raise DataError("Fold train dates must strictly precede test dates.")
    if train_dates != tuple(sorted(set(train_dates))) or test_dates != tuple(
        sorted(set(test_dates))
    ):
        raise DataError("Fold dates must be unique and chronological.")
    available_dates = {s.feature.decision_at for s in samples}
    if (set(train_dates) | set(test_dates)) - available_dates:
        raise DataError("Fold contains unknown dates.")
    fit_at = min(test_dates)
    test_set = set(test_dates)
    test = tuple(i for i, s in enumerate(samples) if s.feature.decision_at in test_set)
    boundary = evaluation_boundary(fit_at)
    buffer = config.gap_dates + config.embargo_dates
    buffered_dates = set(train_dates[-buffer:]) if buffer else set()
    candidates = set(train_dates) - buffered_dates
    bad_dates = {
        s.feature.decision_at
        for s in samples
        if s.feature.decision_at in candidates
        and (s.label is None or s.label.end_at >= boundary or s.label.known_at >= boundary)
    }
    train = tuple(
        i for i, s in enumerate(samples) if s.feature.decision_at in candidates - bad_dates
    )
    purged = tuple(i for i, s in enumerate(samples) if s.feature.decision_at in bad_dates)
    buffered = tuple(i for i, s in enumerate(samples) if s.feature.decision_at in buffered_dates)
    if not train:
        raise DataError("Purging left no known training labels.")
    return Fold(fold_id, stage, train, test, purged, buffered, fit_at)


def walk_forward_folds(samples: tuple[Sample, ...], config: MLConfig) -> tuple[Fold, ...]:
    dates = validate_samples(samples)
    development_end = len(dates) - config.holdout_dates
    if development_end <= config.min_train_dates:
        raise DataError("Insufficient development dates before holdout.")
    folds = []
    for start in range(config.min_train_dates, development_end, config.validation_dates):
        first = max(0, start - config.max_train_dates) if config.max_train_dates else 0
        folds.append(
            purged_fold(
                samples,
                dates[first:start],
                dates[start : min(start + config.validation_dates, development_end)],
                config,
                f"dev-{len(folds)}",
            )
        )
    first = max(0, development_end - config.max_train_dates) if config.max_train_dates else 0
    folds.append(
        purged_fold(
            samples,
            dates[first:development_end],
            dates[development_end:],
            config,
            "final-holdout",
            "holdout",
        )
    )
    return tuple(folds)


def inner_folds(samples: tuple[Sample, ...], outer: Fold, config: MLConfig) -> tuple[Fold, ...]:
    from sklearn.model_selection import TimeSeriesSplit

    # TimeSeriesSplit sees date groups, never flattened asset rows.
    dates = tuple(sorted({samples[i].feature.decision_at for i in outer.train}))
    splitter = TimeSeriesSplit(n_splits=config.inner_splits, test_size=config.inner_test_dates)
    try:
        pairs = list(splitter.split(dates))
    except ValueError as exc:
        raise DataError("Insufficient purged dates for nested TimeSeriesSplit.") from exc
    return tuple(
        purged_fold(
            samples,
            tuple(dates[i] for i in train),
            tuple(dates[i] for i in test),
            config,
            f"{outer.fold_id}/inner-{index}",
            "inner",
        )
        for index, (train, test) in enumerate(pairs)
    )


def fold_audit(fold: Fold, samples: tuple[Sample, ...]) -> dict:
    train, test = [samples[i] for i in fold.train], [samples[i] for i in fold.test]
    return {
        "fold_id": fold.fold_id,
        "stage": fold.stage,
        "fit_at": fold.fit_at,
        "evaluation_boundary": evaluation_boundary(fold.fit_at),
        "train_indices": fold.train,
        "test_indices": fold.test,
        "purged_indices": fold.purged,
        "buffered_indices": fold.buffered,
        "train_start": train[0].feature.decision_at,
        "train_end": train[-1].feature.decision_at,
        "test_start": test[0].feature.decision_at,
        "test_end": test[-1].feature.decision_at,
        "latest_train_label_end": max(s.label.end_at for s in train),
        "latest_train_label_known_at": max(s.label.known_at for s in train),
    }
