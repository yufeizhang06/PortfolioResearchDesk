"""Known-answer and causality checks for the Phase 1 vertical slice."""

from dataclasses import replace
from decimal import Decimal as D

import pytest

from portfolio_research_desk.backtest import run_backtest
from portfolio_research_desk.backtest_config import BacktestConfig, load_backtest_config
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.market_data import load_backtest_dataset


def manual_config() -> BacktestConfig:
    return BacktestConfig(
        initial_cash=D("100"),
        top_k=1,
        max_position_weight=D("1"),
        cash_buffer=D("0"),
        commission_bps=D("0"),
        fixed_fee=D("1"),
        slippage_bps=D("0"),
    )


def test_round_trip_known_answer():
    result = run_backtest(manual_config())
    assert [point.nav for point in result.equity] == list(
        map(D, ["100", "100", "99", "89", "87", "90"])
    )
    assert result.final_state.cash == D("10")
    assert [(p.asset.symbol, p.quantity) for p in result.final_state.positions] == [("SYN_A", 5)]
    assert [fill.quantity for fill in result.fills] == [8, 8, 4, 4, 1, 1, 5]
    assert [fill.side for fill in result.fills] == [
        "BUY",
        "SELL",
        "BUY",
        "SELL",
        "BUY",
        "SELL",
        "BUY",
    ]
    assert result.metrics["total_commission"] == D("7")
    assert result.metrics["cumulative_return"] == D("-0.10")
    assert result.metrics["max_drawdown"] == D("0.13")
    assert result.metrics["traded_notional_over_initial_capital"] == D("5.23")
    for point in result.equity:
        assert point.nav == point.cash + sum((p.market_value for p in point.positions), D("0"))
        assert point.cash >= 0
    for fill in result.fills:
        assert fill.decision_at < fill.execution_at
        assert fill.decision_at.date() < fill.execution_at.date()
    assert sum(order.reason == "NO_NEXT_SESSION" for order in result.orders) == 2


def test_future_perturbation_cannot_change_earlier_decisions_or_fills():
    dataset = load_backtest_dataset()
    changed = replace(
        dataset,
        bars=tuple(
            replace(bar, close=bar.close * 3, high=bar.high * 3)
            if bar.session_date == dataset.sessions[-1].session_date
            else bar
            for bar in dataset.bars
        ),
    )
    original = run_backtest(manual_config(), dataset)
    modified = run_backtest(manual_config(), changed)
    assert original.decisions[:-1] == modified.decisions[:-1]
    assert original.fills == modified.fills
    assert original.equity[:-1] == modified.equity[:-1]


def test_late_input_is_rejected_instead_of_backfilled():
    dataset = load_backtest_dataset()
    changed = replace(
        dataset,
        bars=tuple(
            replace(bar, available_at=bar.available_at.replace(hour=22))
            if bar.session_date == dataset.sessions[1].session_date
            else bar
            for bar in dataset.bars
        ),
    )
    with pytest.raises(DataError, match="available"):
        run_backtest(manual_config(), changed)


def test_small_account_stays_in_cash():
    result = run_backtest(replace(manual_config(), initial_cash=D("1")))
    assert result.fills == ()
    assert all(point.nav == D("1") for point in result.equity)


def test_repeat_run_is_deterministic():
    assert run_backtest(manual_config()) == run_backtest(manual_config())


def test_documented_handcheck_file_matches_known_answer():
    from pathlib import Path

    result = run_backtest(load_backtest_config(Path("configs/example_handcheck.toml")))
    assert result.metrics["ending_nav"] == D("90")
    assert result.metrics["fill_count"] == 7


def test_independent_fill_ledger_reconciles_and_execution_limits_hold():
    config = BacktestConfig()
    dataset = load_backtest_dataset()
    result = run_backtest(config, dataset)
    cash = config.initial_cash
    holdings = {}
    for session in dataset.sessions:
        for fill in result.fills:
            if fill.execution_at == session.open_at:
                sign = 1 if fill.side == "BUY" else -1
                cash -= sign * fill.quantity * fill.price + fill.commission
                holdings[fill.asset] = holdings.get(fill.asset, 0) + sign * fill.quantity
        prices = {b.asset: b.open for b in dataset.bars if b.session_date == session.session_date}
        nav = cash + sum((prices[asset] * q for asset, q in holdings.items()), D("0"))
        assert cash >= config.cash_buffer * nav
        assert all(
            prices[asset] * q <= config.max_position_weight * nav for asset, q in holdings.items()
        )
        assert all(type(q) is int and q >= 0 for q in holdings.values())
    assert cash == result.final_state.cash
    assert {a: q for a, q in holdings.items() if q} == result.final_state.holdings()
