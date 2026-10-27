from dataclasses import replace
from decimal import Decimal as D
from decimal import localcontext

import pytest

from portfolio_research_desk.backtest import run_backtest
from portfolio_research_desk.backtest_config import BacktestConfig
from portfolio_research_desk.domain import PortfolioState, TargetPortfolio
from portfolio_research_desk.errors import DataError, ExecutionError
from portfolio_research_desk.market_data import load_backtest_dataset
from portfolio_research_desk.portfolio import build_target, propose_orders
from portfolio_research_desk.signals import momentum_signals


def test_top_k_equal_weights_leave_constraint_residual_in_cash():
    data = load_backtest_dataset()
    assets = tuple(sorted({b.asset for b in data.bars}))
    signals = momentum_signals(data.bars, assets, data.sessions[1].decision_at, 1)
    target = build_target(signals, BacktestConfig(max_position_weight=D("0.2")))
    assert [(a.symbol, w) for a, w in target.weights] == [("SYN_A", D("0.2")), ("SYN_B", D("0.2"))]
    assert target.cash_weight == D("0.6")
    assert sum((w for _, w in target.weights), target.cash_weight) == 1


def test_future_open_is_not_used_for_decision_share_requests():
    data = load_backtest_dataset()
    assets = tuple(sorted({b.asset for b in data.bars}))
    session = data.sessions[1]
    signals = momentum_signals(data.bars, assets, session.decision_at, 1)
    target = build_target(signals, BacktestConfig())
    current = tuple(b for b in data.bars if b.session_date == session.session_date)
    state = PortfolioState(session.decision_at, D("1000"))
    orders = propose_orders(state, target, current)
    assert [(o.asset.symbol, o.quantity) for o in orders] == [("SYN_A", 40), ("SYN_B", 22)]
    assert all(o.reference_price in (D("11"), D("20")) for o in orders)
    with pytest.raises(DataError, match="available"):
        propose_orders(
            state,
            target,
            tuple(replace(b, available_at=b.available_at.replace(hour=22)) for b in current),
        )


def test_future_signal_and_invalid_weights_are_rejected():
    data = load_backtest_dataset()
    signal = momentum_signals(data.bars, (data.bars[0].asset,), data.sessions[1].decision_at, 1)[0]
    with pytest.raises(DataError, match="available"):
        replace(signal, available_at=data.sessions[2].close_at)
    with pytest.raises(ExecutionError):
        TargetPortfolio(signal.decision_at, ((signal.asset, D("1.1")),), D("-0.1"))


def test_missing_history_and_unknown_symbol_fail_explicitly():
    with pytest.raises(DataError):
        run_backtest(BacktestConfig(lookback_sessions=100))
    with pytest.raises(DataError):
        run_backtest(BacktestConfig(symbols=("SYN_UNKNOWN",), top_k=1))


def test_decimal_context_does_not_change_engine_result():
    expected = run_backtest(BacktestConfig())
    with localcontext() as context:
        context.prec = 8
        assert run_backtest(BacktestConfig()) == expected
