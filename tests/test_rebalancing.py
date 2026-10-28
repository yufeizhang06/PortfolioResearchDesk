from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from decimal import localcontext

import pytest

from portfolio_research_desk.domain import TargetPortfolio, fingerprint
from portfolio_research_desk.errors import DataError, ExecutionError
from portfolio_research_desk.fx import FXBook, FXRate
from portfolio_research_desk.paper_domain import CADState, Costs, Holding
from portfolio_research_desk.paper_execution import simulate_plan
from portfolio_research_desk.paper_sample import CADHistoryStep, example_inputs, run_cad_history
from portfolio_research_desk.portfolio_risk import RiskLimits
from portfolio_research_desk.rebalancing import propose_rebalance


def proposal(**kwargs):
    x = example_inputs()
    state = CADState(x["sessions"][0].open_at, (("CAD", D(3000)), ("USD", D(0))))
    inputs = {k: x[k] for k in ("bundle", "market", "sessions", "decision_at")}
    inputs.update(state=state, plan_id="plan")
    inputs.update(kwargs)
    return x, state, propose_rebalance(**inputs)


def test_default_targets_cash_and_actual_integer_execution_limits():
    x, state, p = proposal()
    assert p.target.cash_weight == D(".4")
    assert all(w == D(".2") for _, w in p.target.weights)
    assert p.estimated_after.violations == ()
    after, fills, value = simulate_plan(state, p, x["execution_market"], x["execution_at"])
    assert value.violations == () and len(fills) == 3
    assert min(after.balances().values()) >= 0
    assert all(f.order.quantity == o.quantity for f, o in zip(fills, p.orders, strict=True))


def test_sector_caps_are_equal_within_sector_and_leave_excess_cash():
    x = example_inputs()
    m = replace(
        x["market"], sectors=tuple(replace(s, name="OneSector") for s in x["market"].sectors)
    )
    _, _, p = proposal(
        market=m,
        limits=RiskLimits(max_positions=2, max_position_weight=D(".6"), max_sector_weight=D(".3")),
    )
    assert len(p.target.weights) == 2
    assert all(w == D(".15") for _, w in p.target.weights)
    assert p.target.cash_weight == D(".70")
    assert p.estimated_after.sector_weights[0][1] <= D(".3")


@pytest.mark.parametrize(
    "limits",
    [
        RiskLimits(max_order_shares=1),
        RiskLimits(max_turnover=D(".05")),
        RiskLimits(max_trade_weight=D(".03")),
        RiskLimits(min_trade_cad=D(10000)),
    ],
)
def test_trade_limits_reduce_or_skip_with_reasons(limits):
    _, _, p = proposal(limits=limits)
    assert p.reasons
    assert all(o.quantity <= limits.max_order_shares for o in p.orders)
    if limits.min_trade_cad == 10000:
        assert not p.orders


def test_small_capital_stays_cash_and_fractional_shares_are_never_requested():
    x = example_inputs()
    state = CADState(x["decision_at"], (("CAD", D(1)), ("USD", D(0))))
    _, _, p = proposal(state=state)
    assert not p.orders and p.estimated_after.nav_cad == 1


def test_custom_target_weights_use_current_positions_and_sells_before_buys():
    x, state, p = proposal()
    state, _, _ = simulate_plan(state, p, x["execution_market"], x["execution_at"])
    # Next after-close decision on Jan 6 with a declared Jan 7 session.
    previous = x["sessions"][1]
    nxt = replace(
        previous,
        session_date=previous.session_date + timedelta(days=1),
        open_at=previous.open_at + timedelta(days=1),
        close_at=previous.close_at + timedelta(days=1),
    )
    at = previous.decision_at
    bundle = replace(
        x["bundle"], signals=tuple(replace(s, decision_at=at) for s in x["bundle"].signals)
    )
    m = replace(
        x["market"],
        quotes=tuple(
            replace(q, observed_at=previous.close_at, available_at=previous.close_at)
            for q in x["market"].quotes
        ),
    )
    target = TargetPortfolio(at, ((bundle.universe.assets[0], D(".1")),), D(".9"))
    p2 = propose_rebalance(state, bundle, m, (previous, nxt), at, "reduce", target=target)
    assert p2.orders and all(o.side == "SELL" for o in p2.orders)
    assert p2.estimated_after.cash_weight >= D(".89")


@pytest.mark.parametrize(
    "case",
    [
        "missing_fx",
        "late_quote",
        "missing_sector",
        "unavailable_sector",
        "late_universe",
        "current_as_pit",
        "descriptive_factor",
        "future_signal_time",
        "duplicate_signal",
        "real_history",
        "mixed_synthetic",
    ],
)
def test_invalid_research_inputs_never_become_orders(case):
    x = example_inputs()
    changes = {}
    if case == "missing_fx":
        changes["market"] = replace(x["market"], fx=FXBook())
    if case == "late_quote":
        changes["market"] = replace(
            x["market"],
            quotes=tuple(
                replace(q, available_at=x["decision_at"] + timedelta(seconds=1))
                for q in x["market"].quotes
            ),
        )
    if case == "missing_sector":
        changes["market"] = replace(x["market"], sectors=())
    if case == "unavailable_sector":
        changes["market"] = replace(
            x["market"],
            sectors=tuple(
                replace(s, available_at=x["decision_at"] + timedelta(seconds=1))
                for s in x["market"].sectors
            ),
        )
    if case in {"late_universe", "current_as_pit"}:
        u = replace(
            x["bundle"].universe,
            available_at=x["decision_at"] + timedelta(seconds=1),
            membership_type="current_snapshot",
        )
        changes["bundle"] = replace(x["bundle"], universe=u)
    if case == "descriptive_factor":
        changes["bundle"] = replace(x["bundle"], descriptive_only=True)
    if case == "future_signal_time":
        changes["bundle"] = replace(
            x["bundle"],
            signals=tuple(replace(s, decision_at=x["execution_at"]) for s in x["bundle"].signals),
        )
    if case == "duplicate_signal":
        changes["bundle"] = replace(x["bundle"], signals=(x["bundle"].signals[0],) * 2)
    if case == "real_history":
        changes.update(mode="backtest", bundle=replace(x["bundle"], data_kind="paper_observed"))
    if case == "mixed_synthetic":
        changes["market"] = replace(
            x["market"], quotes=tuple(replace(q, synthetic=False) for q in x["market"].quotes)
        )
    with pytest.raises((DataError, ExecutionError)):
        proposal(**changes)


@pytest.mark.parametrize(
    "weights,cash", [((D(".3"), D(".3")), D(".4")), ((D(".1"), D(".9")), D(0))]
)
def test_invalid_explicit_targets_rejected(weights, cash):
    x = example_inputs()
    assets = x["bundle"].universe.assets
    target = TargetPortfolio(x["decision_at"], tuple(zip(assets[:2], weights, strict=True)), cash)
    with pytest.raises(ExecutionError):
        proposal(target=target)


@pytest.mark.parametrize(
    "case",
    [
        "same_day",
        "wrong_session",
        "close_quote",
        "missing_held_quote",
        "zero_liquidity",
        "gap",
        "missing_fx",
        "late_fx",
        "stale_state",
        "duplicate_order",
        "funding_gap",
    ],
)
def test_execution_rejects_bad_market_and_temporal_conditions(case):
    x, state, p = proposal()
    m = x["execution_market"]
    at = x["execution_at"]
    if case == "same_day":
        at = x["decision_at"]
    if case == "wrong_session":
        at += timedelta(days=1)
    if case == "close_quote":
        m = replace(m, quotes=tuple(replace(q, kind="close") for q in m.quotes))
    if case == "missing_held_quote":
        m = replace(m, quotes=())
    if case == "zero_liquidity":
        m = replace(m, quotes=tuple(replace(q, volume=0) for q in m.quotes))
    if case == "gap":
        m = replace(m, quotes=tuple(replace(q, price=q.price * 2) for q in m.quotes))
    if case == "missing_fx":
        m = replace(m, fx=FXBook())
    if case == "late_fx":
        m = replace(
            m,
            fx=FXBook(
                tuple(replace(r, available_at=at + timedelta(seconds=1)) for r in m.fx.rates)
            ),
        )
    if case == "stale_state":
        state = replace(state, cash=(("CAD", D(2000)), ("USD", D(0))))
    if case == "duplicate_order":
        p = replace(p, orders=(p.orders[0], p.orders[0]))
    if case == "funding_gap":
        # Large FX move is available only at execution, so the fixed share requests fail risk.
        m = replace(m, fx=FXBook(tuple(replace(r, cad_per_usd=D(20)) for r in m.fx.rates)))
    with pytest.raises((ExecutionError, DataError)):
        simulate_plan(state, p, m, at)


def test_future_fx_vintages_and_prices_cannot_change_previous_plan():
    x, state, p = proposal()
    future = FXRate(x["execution_at"], x["execution_at"], D(99), "future", True)
    m = replace(x["market"], fx=FXBook((*x["market"].fx.rates, future)))
    _, _, p2 = proposal(market=m)
    assert (
        p.target == p2.target and p.orders == p2.orders and p.estimated_after == p2.estimated_after
    )
    assert fingerprint(state) == p.state_hash


def test_cad_backtest_and_paper_share_target_sizing_costs_and_execution():
    x, state, p = proposal()
    end, fills, value = simulate_plan(state, p, x["execution_market"], x["execution_at"])
    step = CADHistoryStep(
        x["bundle"],
        x["market"],
        x["sessions"],
        x["decision_at"],
        x["execution_market"],
        x["execution_market"],
        x["execution_at"],
    )
    actual, records = run_cad_history(state, (step,))
    assert actual == end and records[0]["valuation"] == value
    assert records[0]["plan"].mode == "backtest" and p.mode == "paper"
    assert [(f.order.asset, f.order.quantity, f.price, f.commission_local) for f in fills] == [
        (f.order.asset, f.order.quantity, f.price, f.commission_local) for f in records[0]["fills"]
    ]


def test_planning_decimal_context_is_fixed():
    _, _, expected = proposal()
    with localcontext() as context:
        context.prec = 6
        _, _, actual = proposal()
    assert actual == expected


@pytest.mark.parametrize("case", ["empty", "unsorted", "duplicate", "intraday", "no_next"])
def test_session_manifest_errors(case):
    x = example_inputs()
    if case == "empty":
        sessions = ()
    elif case == "unsorted":
        sessions = tuple(reversed(x["sessions"]))
    elif case == "duplicate":
        sessions = (x["sessions"][0],) * 2
    elif case == "no_next":
        sessions = (x["sessions"][0],)
    else:
        with pytest.raises((DataError, ExecutionError)):
            proposal(decision_at=x["sessions"][0].open_at)
        return
    with pytest.raises((DataError, ExecutionError)):
        proposal(sessions=sessions)


def test_high_fixed_fee_sale_uses_largest_feasible_request_without_false_binary_bound():
    x = example_inputs()
    asset = x["market"].quotes[1].asset
    market = replace(
        x["market"],
        quotes=tuple(
            replace(q, price=D(100)) if q.asset == asset else q for q in x["market"].quotes
        ),
    )
    state = CADState(x["sessions"][0].open_at, positions=(Holding(asset, 2, D(200), D(200)),))
    limits = RiskLimits(
        max_position_weight=D(1), max_sector_weight=D(1), max_trade_weight=D(1), cash_buffer=D(".1")
    )
    costs = Costs(D(150), D(0), D(0), D(0))
    target = TargetPortfolio(x["decision_at"], (), D(1))
    _, _, plan = proposal(state=state, market=market, limits=limits, costs=costs, target=target)
    assert len(plan.orders) == 1 and plan.orders[0].side == "SELL" and plan.orders[0].quantity == 2
    assert plan.estimated_after.nav_cad == 50 and plan.estimated_after.cash_weight == 1


@pytest.mark.parametrize("component", ["quote", "fx"])
def test_synthetic_paper_plan_cannot_fill_with_real_inputs(component):
    x, state, plan = proposal()
    market = x["execution_market"]
    if component == "quote":
        market = replace(market, quotes=tuple(replace(q, synthetic=False) for q in market.quotes))
    else:
        market = replace(
            market, fx=FXBook(tuple(replace(r, synthetic=False) for r in market.fx.rates))
        )
    with pytest.raises(ExecutionError, match="cannot mix real"):
        simulate_plan(state, plan, market, x["execution_at"])


def test_history_returned_state_advances_through_valuation_clock():
    x, state, _ = proposal()
    at = x["sessions"][1].close_at
    close = replace(
        x["execution_market"],
        quotes=tuple(
            replace(q, kind="close", observed_at=at, available_at=at)
            for q in x["execution_market"].quotes
        ),
    )
    step = CADHistoryStep(
        x["bundle"], x["market"], x["sessions"], x["decision_at"], x["execution_market"], close, at
    )
    final, records = run_cad_history(state, (step,))
    assert final.as_of == records[0]["valuation"].as_of == at
