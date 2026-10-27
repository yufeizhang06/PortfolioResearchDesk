"""Exhaustive fold boundaries and global-date panel separation."""

from dataclasses import replace
from datetime import timedelta

import pytest

from portfolio_research_desk.errors import DataError
from portfolio_research_desk.ml_config import MLConfig
from portfolio_research_desk.ml_data import build_samples, synthetic_ml_dataset
from portfolio_research_desk.ml_models import fit_model
from portfolio_research_desk.ml_validation import (
    inner_folds,
    purged_fold,
    validate_fold,
    validate_samples,
    walk_forward_folds,
)


@pytest.fixture(scope="module")
def panel():
    return synthetic_ml_dataset(320)


@pytest.mark.parametrize("horizon", [1, 5, 10])
@pytest.mark.parametrize("gap,embargo", [(0, 0), (1, 2), (10, 0)])
@pytest.mark.parametrize("rolling", [0, 100])
def test_every_outer_and_inner_boundary_independently(panel, horizon, gap, embargo, rolling):
    config = MLConfig(
        horizon=horizon, gap_dates=gap, embargo_dates=embargo, max_train_dates=rolling
    )
    samples = build_samples(panel, horizon)
    outer = walk_forward_folds(samples, config)
    assert outer[-1].stage == "holdout"
    assert len({samples[i].feature.decision_at for i in outer[-1].test}) == config.holdout_dates
    test_sets = []
    for fold in outer:
        test_sets.extend(fold.test)
        for check in (fold, *inner_folds(samples, fold, config)):
            validate_fold(samples, check)
            training = [samples[i] for i in check.train]
            validation = [samples[i] for i in check.test]
            boundary = min(s.feature.observation_end for s in validation)
            assert max(s.feature.decision_at for s in training) < min(
                s.feature.decision_at for s in validation
            )
            assert max(s.label.end_at for s in training) < boundary
            assert max(s.label.known_at for s in training) <= check.fit_at
            assert {s.feature.decision_at for s in training}.isdisjoint(
                s.feature.decision_at for s in validation
            )
            for indices in (check.train, check.test, check.purged, check.buffered):
                assert len(indices) % 3 == 0
            assert len(check.buffered) == 3 * (gap + embargo)
            if rolling:
                assert len({s.feature.decision_at for s in training}) <= rolling
    assert len(test_sets) == len(set(test_sets))


@pytest.mark.parametrize("problem", ["end_overlap", "late_known", "unavailable"])
def test_purge_whole_date_for_one_bad_asset(panel, problem):
    config = MLConfig(gap_dates=0, embargo_dates=0)
    samples = list(build_samples(panel))
    dates = validate_samples(tuple(samples))
    index = 3 * 40
    label = samples[index].label
    if problem == "end_overlap":
        label = replace(label, end_at=dates[100], known_at=dates[101])
    elif problem == "late_known":
        label = replace(label, known_at=dates[101])
    else:
        label = None
    samples[index] = replace(samples[index], label=label)
    fold = purged_fold(tuple(samples), dates[:100], dates[100:120], config, "bad-date")
    assert set(range(index, index + 3)) <= set(fold.purged)
    assert not set(range(index, index + 3)) & set(fold.train)


def test_schema_order_missing_and_duplicate_rejected(panel):
    samples = build_samples(panel)
    for changed in ((), samples[1:], samples[::-1], samples + samples[-1:]):
        with pytest.raises(DataError):
            validate_samples(changed)
    dates = validate_samples(samples)
    for train, test in (
        (dates[:100], dates[99:120]),
        ((), dates[100:120]),
        (dates[:100][::-1], dates[100:120]),
        (dates[:100], (dates[-1] + timedelta(days=10),)),
    ):
        with pytest.raises(DataError):
            purged_fold(samples, train, test, MLConfig(), "bad")


def test_forged_fold_cannot_bypass_model_time_guard(panel):
    samples = build_samples(panel)
    fold = walk_forward_folds(samples, MLConfig())[0]
    for forged in (
        replace(fold, train=fold.train + fold.test[:1]),
        replace(fold, fit_at=fold.fit_at + timedelta(days=1)),
        replace(fold, train=(len(samples),)),
        replace(fold, train=()),
        replace(fold, train=tuple(range(fold.test[0]))),
    ):
        with pytest.raises(DataError):
            fit_model("logistic", {"C": 1}, 42, samples, forged)


def test_no_labels_left_and_insufficient_nested_history(panel):
    samples = tuple(replace(s, label=None) for s in build_samples(panel))
    dates = validate_samples(samples)
    with pytest.raises(DataError, match="no known"):
        purged_fold(samples, dates[:100], dates[100:120], MLConfig(), "empty")
    samples = build_samples(panel)
    fold = walk_forward_folds(samples, MLConfig())[0]
    with pytest.raises(DataError, match="Insufficient"):
        inner_folds(samples, replace(fold, train=fold.train[:12]), MLConfig())
