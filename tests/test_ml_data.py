"""Independent feature/label arithmetic and fail-closed timing contracts."""

import math
from dataclasses import replace
from datetime import timedelta
from decimal import localcontext
from fractions import Fraction

import pytest

from portfolio_research_desk.errors import DataError
from portfolio_research_desk.ml_data import build_samples, synthetic_ml_dataset


def test_independent_feature_and_label_arithmetic():
    dataset = synthetic_ml_dataset(100)
    samples = build_samples(dataset)
    first = samples[0]
    history = [b for b in dataset.bars if b.asset == first.feature.asset]
    prices = [Fraction(b.close) for b in history]
    expected = [float(prices[60] / prices[60 - lag] - 1) for lag in (5, 20, 60)]
    changes = [prices[i] / prices[i - 1] - 1 for i in range(1, 61)]
    for width in (20, 60):
        window = changes[-width:]
        average = sum(window) / width
        expected.append(math.sqrt(float(sum((x - average) ** 2 for x in window) / (width - 1))))
    expected.append(
        math.log1p(float(sum(Fraction(b.close) * b.volume for b in history[41:61]) / 20))
    )
    market = (
        sum(
            Fraction(b.close) / Fraction(dataset.bars[40 * 3 + j].close) - 1
            for j, b in enumerate(dataset.bars[60 * 3 : 61 * 3])
        )
        / 3
    )
    expected.append(float(prices[60] / prices[40] - 1 - market))
    assert first.feature.values == pytest.approx(expected, rel=1e-12, abs=1e-14)
    assert first.label.forward_return == pytest.approx(
        float(Fraction(history[66].open) / Fraction(history[61].open) - 1)
    )
    assert first.label.start_at == dataset.sessions[61].open_at
    assert first.label.end_at == dataset.sessions[66].open_at
    assert first.label.known_at == history[66].available_at
    assert sum(s.label is None for s in samples) == 18


def test_future_prices_cannot_change_prior_features():
    dataset = synthetic_ml_dataset(100)
    original = build_samples(dataset)
    cutoff = dataset.sessions[85].session_date
    modified = replace(
        dataset,
        bars=tuple(
            replace(b, close=b.close * 2, high=b.high * 2) if b.session_date >= cutoff else b
            for b in dataset.bars
        ),
    )
    changed = build_samples(modified)
    assert [s.feature for s in original if s.feature.decision_at.date() < cutoff] == [
        s.feature for s in changed if s.feature.decision_at.date() < cutoff
    ]


@pytest.mark.parametrize("field", ["observation_end", "available_at"])
def test_deliberately_leaking_tomorrow_feature_is_rejected(field):
    feature = build_samples(synthetic_ml_dataset(100))[0].feature
    with pytest.raises(DataError, match="future|unavailable"):
        replace(feature, **{field: feature.decision_at + timedelta(days=1)})


def test_late_cross_asset_market_input_is_rejected():
    dataset = synthetic_ml_dataset(100)
    late = replace(dataset.bars[60 * 3 + 2], available_at=dataset.sessions[61].decision_at)
    with pytest.raises(DataError, match="unavailable"):
        build_samples(replace(dataset, bars=dataset.bars[:182] + (late,) + dataset.bars[183:]))


@pytest.mark.parametrize("source", ["French", "retrieved_snapshot", "rolling_beta"])
def test_phase3_and_unverified_features_cannot_enter_signals(source):
    feature = build_samples(synthetic_ml_dataset(100))[0].feature
    with pytest.raises(DataError, match="provenance"):
        replace(feature, source=source)


@pytest.mark.parametrize("kind", ["missing_open", "suspended", "zero_volume"])
def test_unexecutable_label_endpoints_are_excluded(kind):
    dataset = synthetic_ml_dataset(100)
    changes = {
        "missing_open": {"open": None},
        "suspended": {"tradable": False},
        "zero_volume": {"volume": 0},
    }[kind]
    bars = list(dataset.bars)
    bars[66 * 3] = replace(bars[66 * 3], **changes)
    assert build_samples(replace(dataset, bars=tuple(bars)))[0].label is None


def test_invalid_label_and_sample_and_feature_schema():
    sample = build_samples(synthetic_ml_dataset(100))[0]
    for updates in (
        {"known_at": sample.label.start_at},
        {"end_at": sample.label.start_at},
        {"forward_return": float("nan")},
        {"forward_return": -1},
    ):
        with pytest.raises(DataError):
            replace(sample.label, **updates)
    with pytest.raises(DataError, match="mismatch"):
        replace(
            sample,
            label=replace(sample.label, decision_at=sample.label.decision_at - timedelta(days=1)),
        )
    for values in ((1.0,), (float("nan"),) * 7, (float("inf"),) * 7):
        with pytest.raises(DataError, match="schema"):
            replace(sample.feature, values=values)


@pytest.mark.parametrize(
    "change", [{"synthetic": False}, {"source": "Yahoo"}, {"corporate_actions": "unknown"}]
)
def test_unverified_market_inputs_blocked(change):
    with pytest.raises(DataError):
        build_samples(replace(synthetic_ml_dataset(100), **change))


def test_decimal_context_cannot_change_fixture_or_features():
    expected = synthetic_ml_dataset(100)
    samples = build_samples(expected)
    with localcontext() as context:
        context.prec = 3
        context.Emax = 5
        assert synthetic_ml_dataset(100) == expected
        assert build_samples(expected) == samples


@pytest.mark.parametrize("horizon", [0, -1, True])
def test_invalid_horizon(horizon):
    with pytest.raises(DataError):
        build_samples(synthetic_ml_dataset(100), horizon)


def test_short_history_and_invalid_session_count():
    with pytest.raises(DataError):
        synthetic_ml_dataset(2)
    with pytest.raises(DataError, match="62"):
        build_samples(synthetic_ml_dataset(61))
