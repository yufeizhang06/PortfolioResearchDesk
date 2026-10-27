from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal as D
from decimal import localcontext
from importlib.resources import files
from pathlib import Path

import pytest

from portfolio_research_desk.data_adapters import LocalHistoryAdapter
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.factor_data import FactorData, FactorRow, combine_factors
from portfolio_research_desk.factor_returns import (
    ReturnData,
    ReturnRow,
    align_common_sample,
    calculate_returns,
)


@pytest.fixture
def inputs():
    root = files("portfolio_research_desk").joinpath("resources")
    history = LocalHistoryAdapter(Path(str(root.joinpath("factor_prices.csv")))).read()
    factors = combine_factors(
        root.joinpath("factors_ff3.csv").read_bytes(),
        root.joinpath("factors_mom.csv").read_bytes(),
        "daily",
        datetime(2024, 6, 1, tzinfo=UTC),
        "synthetic",
        True,
    )
    return history, factors


def test_prices_to_simple_returns_and_same_period_rf_without_double_subtraction(inputs):
    history, factors = inputs
    returns = calculate_returns(history, factors)
    aligned = align_common_sample(returns, factors, date(2024, 1, 2), date(2024, 6, 1))
    assert len(aligned.rows) == 96
    first = aligned.rows[0]
    actual = history.rows[1].adj_close / history.rows[0].adj_close - 1
    assert first.stock_return == pytest.approx(float(actual))
    assert first.excess_return == pytest.approx(float(actual - factors.rows[1].rf))
    assert first.factors[0] == float(factors.rows[1].mkt_rf)


def test_missing_momentum_drops_identical_period_for_both_models(inputs):
    history, factors = inputs
    changed = replace(
        factors,
        rows=tuple(replace(r, mom=None) if i == 10 else r for i, r in enumerate(factors.rows)),
    )
    sample = align_common_sample(
        calculate_returns(history, changed), changed, date(2024, 1, 2), date(2024, 6, 1)
    )
    assert len(sample.rows) == 95
    assert sample.exclusions == (
        {"period": str(factors.rows[10].period), "reason": "MISSING_FACTOR_VALUE"},
    )


def test_missing_price_does_not_create_multiday_return(inputs):
    history, factors = inputs
    missing = history.rows[10].session_date
    history = replace(history, rows=tuple(r for r in history.rows if r.session_date != missing))
    returns = calculate_returns(history, factors)
    assert missing not in {r.period for r in returns.rows}
    assert factors.rows[11].period not in {r.period for r in returns.rows}
    assert len(returns.rows) == 94


def test_missing_factor_date_retains_price_intervals_and_reports_exclusion(inputs):
    history, factors = inputs
    missing = factors.rows[10].period
    changed = replace(factors, rows=tuple(r for r in factors.rows if r.period != missing))
    original = calculate_returns(history, factors)
    returns = calculate_returns(history, changed)
    assert returns.rows == original.rows
    sample = align_common_sample(returns, changed, date(2024, 1, 2), date(2024, 6, 1))
    assert {"period": str(missing), "reason": "MISSING_FACTOR_DATE"} in sample.exclusions


def test_invalid_multiday_return_and_mixed_frequencies_are_not_matched(inputs):
    history, factors = inputs
    returns = calculate_returns(history, factors)
    modified = replace(returns, rows=(replace(returns.rows[2], start=returns.rows[0].start),))
    sample = align_common_sample(modified, factors, modified.rows[0].period, factors.rows[4].period)
    assert sample.rows == ()
    assert sample.exclusions[0]["reason"] == "RETURN_INTERVAL_MISMATCH"
    with pytest.raises(DataError, match="frequency"):
        align_common_sample(
            replace(returns, frequency="monthly", rows=()),
            factors,
            date(2024, 1, 1),
            date(2024, 6, 1),
        )


def test_action_handling_missing_adjusted_prices_and_future_prices(inputs):
    history, factors = inputs
    action = replace(
        history,
        rows=tuple(replace(r, dividend=D(1)) if i == 10 else r for i, r in enumerate(history.rows)),
    )
    assert len(calculate_returns(action, factors, "close").rows) == 95
    assert len(calculate_returns(action, factors, "adjusted_close").rows) == 96
    missing = replace(
        history,
        rows=tuple(
            replace(r, adj_close=None) if i == 10 else r for i, r in enumerate(history.rows)
        ),
    )
    assert len(calculate_returns(missing, factors).rows) == 94
    boundary = history.rows[40].session_date
    future = replace(
        history,
        rows=tuple(
            replace(r, adj_close=r.adj_close * D(3)) if r.session_date > boundary else r
            for r in history.rows
        ),
    )
    assert [r for r in calculate_returns(future, factors).rows if r.period <= boundary] == [
        r for r in calculate_returns(history, factors).rows if r.period <= boundary
    ]


def test_monthly_returns_use_declared_last_sessions_and_previous_month(inputs):
    history, _ = inputs
    days = [date(2023, 12, 29), date(2024, 1, 30), date(2024, 1, 31), date(2024, 2, 29)]
    stamp = datetime(2024, 6, 1, tzinfo=UTC)
    rows = tuple(
        replace(
            history.rows[0],
            session_date=d,
            event_time=datetime(d.year, d.month, d.day, 22, tzinfo=UTC),
            observation_end=datetime(d.year, d.month, d.day, 22, tzinfo=UTC),
            open=D(v),
            high=D(v),
            low=D(v),
            close=D(v),
            adj_close=D(v),
        )
        for d, v in zip(days, [100, 105, 110, 121], strict=True)
    )
    history = replace(history, rows=rows)
    factors = FactorData(
        "monthly",
        tuple(
            FactorRow(d, D(".01"), D(".02"), D(".03"), D(".001"), D(".04"))
            for d in [date(2024, 1, 31), date(2024, 2, 29)]
        ),
        "synthetic",
        stamp,
        {},
        True,
    )
    with pytest.raises(DataError, match="calendar"):
        calculate_returns(history, factors)
    returns = calculate_returns(history, factors, sessions=tuple(days))
    assert [r.value for r in returns.rows] == [D(".1"), D(".1")]
    aligned = align_common_sample(returns, factors, date(2024, 1, 1), date(2024, 3, 1))
    assert [r.excess_return for r in aligned.rows] == pytest.approx([0.099, 0.099])
    # Missing January endpoint cannot silently substitute January 30.
    incomplete = replace(history, rows=tuple(r for r in history.rows if r.session_date != days[2]))
    assert calculate_returns(incomplete, factors, sessions=tuple(days)).rows == ()


def test_input_identity_and_duplicate_return_dates_are_rejected(inputs):
    history, factors = inputs
    with pytest.raises(DataError, match="mixed"):
        calculate_returns(history, replace(factors, synthetic=False))
    row = ReturnRow(date(2024, 1, 2), date(2024, 1, 1), D(".1"), history.retrieved_at)
    with pytest.raises(DataError, match="unique"):
        ReturnData(history.rows[0].asset, "daily", (row, row), "close", "hash", ())


def test_caller_decimal_precision_cannot_change_returns_or_excess_returns(inputs):
    history, factors = inputs
    expected = calculate_returns(history, factors)
    aligned = align_common_sample(expected, factors, date(2024, 1, 2), date(2024, 6, 1))
    with localcontext() as context:
        context.prec = 6
        actual = calculate_returns(history, factors)
        assert actual == expected
        assert align_common_sample(actual, factors, date(2024, 1, 2), date(2024, 6, 1)) == aligned
