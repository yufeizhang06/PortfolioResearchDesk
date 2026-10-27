from dataclasses import replace
from decimal import Decimal as D

import pytest

from portfolio_research_desk.backtest_config import BacktestConfig
from portfolio_research_desk.domain import OrderProposal, PortfolioState, Position
from portfolio_research_desk.errors import ExecutionError
from portfolio_research_desk.execution import execute_orders
from portfolio_research_desk.market_data import load_backtest_dataset


def scenario():
    data = load_backtest_dataset()
    session = data.sessions[2]
    bars = tuple(b for b in data.bars if b.session_date == session.session_date)
    asset = bars[0].asset
    decision = data.sessions[1].decision_at
    state = PortfolioState(decision, D("100"))
    config = BacktestConfig(
        top_k=1,
        max_position_weight=D("1"),
        cash_buffer=D("0"),
        commission_bps=D("0"),
        fixed_fee=D("1"),
        slippage_bps=D("0"),
    )
    order = OrderProposal("known", asset, "BUY", 9, decision, D("11"))
    return session, bars, state, config, order


def test_gap_and_fee_reduce_requested_shares_without_borrowing():
    session, bars, state, config, order = scenario()
    result = execute_orders(state, (order,), bars, session, config)
    assert result.fills[0].quantity == 8
    assert result.fills[0].price == D("12")
    assert result.state.cash == D("3")
    assert result.orders[0].status == "PARTIAL"
    assert state.cash == D("100") and not state.positions


def test_cheap_future_open_cannot_increase_the_original_request():
    session, bars, state, config, order = scenario()
    bars = (replace(bars[0], open=D("1"), low=D("1")), *bars[1:])
    result = execute_orders(state, (order,), bars, session, config)
    assert result.fills[0].quantity == order.quantity == 9
    assert result.state.cash == D("90")


def test_adverse_slippage_and_conservative_cent_fee_rounding():
    session, bars, state, config, order = scenario()
    config = replace(config, fixed_fee=D("0.50"), commission_bps=D("10"), slippage_bps=D("100"))
    result = execute_orders(state, (replace(order, quantity=1),), bars, session, config)
    assert result.fills[0].price == D("12.12")
    assert result.fills[0].commission == D("0.52")
    assert result.fills[0].slippage_cost == D("0.12")
    assert result.state.cash == D("87.36")
    # A new, later decision is required; a repeated same-batch sell is not an intraday strategy.
    later_session = load_backtest_dataset().sessions[3]
    later_bars = tuple(
        replace(
            b,
            session_date=later_session.session_date,
            open_at=later_session.open_at,
            event_time=later_session.close_at,
            observation_end=later_session.close_at,
            available_at=later_session.decision_at,
        )
        for b in bars
    )
    sell = replace(order, order_id="sell", side="SELL", quantity=1, decision_at=session.decision_at)
    closed = execute_orders(result.state, (sell,), later_bars, later_session, config)
    assert closed.fills[0].price == D("11.88")
    assert closed.state.cash == D("98.72")
    assert not closed.state.positions


def test_weight_and_cash_caps_apply_to_actual_post_cost_nav():
    session, bars, state, config, order = scenario()
    config = replace(config, max_position_weight=D("0.5"), cash_buffer=D("0.5"))
    result = execute_orders(state, (order,), bars, session, config)
    assert result.fills[0].quantity == 4
    assert result.state.cash == D("51")
    assert D("48") <= D("0.5") * D("99")


@pytest.mark.parametrize(
    "kind", ["same_session", "oversell", "duplicate", "future_state", "currency"]
)
def test_illegal_execution_is_rejected(kind):
    session, bars, state, config, order = scenario()
    orders = (order,)
    if kind == "same_session":
        orders = (replace(order, decision_at=session.decision_at),)
    elif kind == "oversell":
        orders = (replace(order, side="SELL"),)
    elif kind == "duplicate":
        orders = (order, order)
    elif kind == "future_state":
        state = replace(state, as_of=session.decision_at)
    else:
        orders = (replace(order, asset=replace(order.asset, currency="CAD")),)
    with pytest.raises(ExecutionError):
        execute_orders(state, orders, bars, session, config)


@pytest.mark.parametrize("kind", ["missing_open", "suspended", "missing_quote", "no_next"])
def test_non_executable_orders_are_cancelled(kind):
    session, bars, state, config, order = scenario()
    if kind == "missing_open":
        bars = (replace(bars[0], open=None), *bars[1:])
    elif kind == "suspended":
        bars = (replace(bars[0], tradable=False, volume=0), *bars[1:])
    elif kind == "missing_quote":
        bars = bars[1:]
    else:
        session = None
    result = execute_orders(state, (order,), bars, session, config)
    assert not result.fills
    assert result.state.cash == state.cash
    assert result.orders[0].status == "CANCELLED"


def test_missing_held_open_cancels_batch_without_stale_risk_marks():
    session, bars, state, config, order = scenario()
    state = replace(state, positions=(Position(order.asset, 1),))
    bars = (replace(bars[0], open=None), *bars[1:])
    result = execute_orders(state, (order,), bars, session, config)
    assert result.state == state
    assert result.orders[0].reason == "UNAVAILABLE_HELD_OPEN"


def test_unresolvable_existing_open_weight_breach_fails_closed():
    session, bars, state, config, order = scenario()
    state = replace(state, cash=D("4"), positions=(Position(order.asset, 8),))
    config = replace(config, max_position_weight=D("0.5"))
    with pytest.raises(ExecutionError, match="infeasible"):
        execute_orders(state, (order,), bars, session, config)


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True])
def test_orders_require_positive_integer_shares(quantity):
    *_, order = scenario()
    with pytest.raises(ExecutionError):
        replace(order, quantity=quantity)
