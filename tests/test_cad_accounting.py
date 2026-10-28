"""Independent hand/Fraction oracles, separate from planner and ledger replay."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from decimal import localcontext
from fractions import Fraction as F

import pytest

from portfolio_research_desk.domain import OrderProposal
from portfolio_research_desk.errors import DataError, ExecutionError
from portfolio_research_desk.fx import FXBook, FXRate
from portfolio_research_desk.paper_domain import CADState, Costs, Holding
from portfolio_research_desk.paper_execution import cash_flow, convert_cash, corporate_action, trade
from portfolio_research_desk.paper_sample import example_inputs
from portfolio_research_desk.portfolio_risk import RiskLimits, value_portfolio


def handcase():
    x = example_inputs()
    at = x["decision_at"]
    a, b, _ = x["bundle"].universe.assets
    market = replace(x["market"], fx=FXBook((FXRate(at, at, D("1.25"), "hand", True),)))
    limits = RiskLimits(
        max_position_weight=D("1"),
        max_sector_weight=D("1"),
        cash_buffer=D("0"),
        max_trade_weight=D("1"),
        max_price_deviation=D("1"),
    )
    costs = Costs(D("1"), D("0"), D("0"), D("100"))
    state = CADState(at, (("CAD", D("1000")), ("USD", D("0"))), net_contributions_cad=D("1000"))
    return x, a, b, market, limits, costs, state


def order(asset, side, q, at, price, identifier="hand"):
    return OrderProposal(identifier, asset, side, q, at, D(price))


def test_two_currency_hand_ledger_and_fx_translation():
    x, a, b, m, limits, c, s = handcase()
    s, f1 = trade(s, order(a, "BUY", 32, s.as_of, "10"), m, s.as_of, c, limits)
    assert s.balances()["CAD"] == D("594.73")  # 321 USD * 1.25 = 401.25 + 4.02 fee
    assert f1.conversion.source_amount == D("401.25")
    assert f1.conversion.fee_cad == D("4.02")
    s, f2 = trade(s, order(b, "BUY", 15, s.as_of, "20", "cad"), m, s.as_of, c, limits)
    assert s.balances() == {"CAD": D("293.73"), "USD": D("0")}
    assert value_portfolio(s, m, s.as_of, limits).nav_cad == D("993.73")
    assert s.commission_cad == D("2.25") and s.fx_cost_cad == D("4.02")
    at = x["execution_at"]
    marks = tuple(
        replace(
            q,
            price=D("11") if q.asset == a else D("19") if q.asset == b else q.price,
            observed_at=at,
            available_at=at,
            kind="mark",
        )
        for q in m.quotes
    )
    m2 = replace(m, quotes=marks, fx=FXBook((FXRate(at, at, D("1.30"), "hand2", True),)))
    result = value_portfolio(s, m2, at, limits)
    expected = F(29373, 100) + 32 * 11 * F(13, 10) + 15 * 19
    assert F(result.nav_cad) == expected == F(103633, 100)
    assert result.nav_cad != D("1036.33") - s.commission_cad - s.fx_cost_cad
    for p in result.positions:
        rate = D("1.30") if p["asset"].currency == "USD" else D("1")
        assert p["cad_pnl"] == p["local_pnl"] * rate + p["fx_translation_cad"]


@pytest.mark.parametrize("source", ["CAD", "USD"])
def test_cash_conversion_nav_loss_equals_fee_plus_rounding(source):
    _, _, _, m, limits, c, s = handcase()
    if source == "USD":
        s = replace(s, cash=(("CAD", D("0")), ("USD", D("100"))))
    before = value_portfolio(s, m, s.as_of, limits).nav_cad
    after, conversion = convert_cash(s, source, D("10.01"), m.fx, s.as_of, c, limits)
    assert (
        before - value_portfolio(after, m, s.as_of, limits).nav_cad
        == conversion.fee_cad + conversion.rounding_cad
    )
    assert min(after.balances().values()) >= 0


def test_existing_usd_is_spent_without_charging_fx_again_and_sales_remain_usd():
    _, a, _, m, limits, c, s = handcase()
    s = replace(s, cash=(("CAD", D("1000")), ("USD", D("100"))))
    bought, f = trade(s, order(a, "BUY", 5, s.as_of, "10"), m, s.as_of, c, limits)
    assert f.conversion is None and bought.balances()["USD"] == D("49")
    sold, f = trade(bought, order(a, "SELL", 5, s.as_of, "10"), m, s.as_of, c, limits)
    assert f.conversion is None and sold.balances()["USD"] == D("98")
    assert sold.fx_cost_cad == 0 and not sold.positions
    assert sold.realized_pnl_cad == D("-2.50")


@pytest.mark.parametrize("shares", [1, 2, 7, 31, 32])
@pytest.mark.parametrize("fx", ["1.234567", "1.25", "1.36"])
def test_fraction_oracle_for_fills_commission_slippage_fx_and_nav(shares, fx):
    _, a, _, m, limits, _, s = handcase()
    rate = FXRate(s.as_of, s.as_of, D(fx), "oracle", True)
    m = replace(m, fx=FXBook((rate,)))
    c = Costs(D("0.11"), D("13"), D("7"), D("19"))
    after, f = trade(s, order(a, "BUY", shares, s.as_of, "10"), m, s.as_of, c, limits)

    def ceilcent(x):
        return F(-(-x.numerator * 100 // x.denominator), 100)

    fill_price = ceilcent(F(10) * (1 + F(7, 10000)))
    fee = ceilcent(F(11, 100) + shares * fill_price * F(13, 10000))
    usd = shares * fill_price + fee
    principal = ceilcent(usd * F(fx))
    fxfee = ceilcent(principal * F(19, 10000))
    cash = F(1000) - principal - fxfee
    assert F(after.balances()["CAD"]) == cash
    assert F(f.price) == fill_price and F(f.commission_local) == fee
    expected_nav = cash + shares * 10 * F(fx)
    assert F(value_portfolio(after, m, s.as_of, limits).nav_cad) == expected_nav


def test_partial_average_cost_sales_and_full_liquidation_leave_no_basis_residue():
    _, a, _, m, limits, c, s = handcase()
    s, _ = trade(s, order(a, "BUY", 3, s.as_of, "10"), m, s.as_of, c, limits)
    original = s.positions[0].cost_cad
    s, _ = trade(s, order(a, "SELL", 1, s.as_of, "10"), m, s.as_of, c, limits)
    assert abs(s.positions[0].cost_cad - original * D(2) / D(3)) < D("1e-25")
    s, _ = trade(s, order(a, "SELL", 2, s.as_of, "10"), m, s.as_of, c, limits)
    assert s.positions == ()


def test_split_and_raw_dividend_do_not_double_count_nav():
    _, a, _, m, limits, c, s = handcase()
    s, _ = trade(s, order(a, "BUY", 4, s.as_of, "10"), m, s.as_of, c, limits)
    old_nav = value_portfolio(s, m, s.as_of, limits).nav_cad
    split_at = s.as_of + timedelta(seconds=1)
    dividend_at = split_at + timedelta(seconds=1)
    split = corporate_action(s, a, "SPLIT", D(2), split_at, s.as_of, m.fx, limits)
    split_market = replace(
        m, quotes=tuple(replace(q, price=D(5)) if q.asset == a else q for q in m.quotes)
    )
    assert split.positions[0].quantity == 8
    assert split.positions[0].cost_cad == s.positions[0].cost_cad
    assert value_portfolio(split, split_market, split_at, limits).nav_cad == old_nav
    dividend = corporate_action(split, a, "DIVIDEND", D("0.50"), dividend_at, s.as_of, m.fx, limits)
    exdiv = replace(
        split_market,
        quotes=tuple(
            replace(q, price=D("4.50")) if q.asset == a else q for q in split_market.quotes
        ),
    )
    assert value_portfolio(dividend, exdiv, dividend_at, limits).nav_cad == old_nav
    assert dividend.dividends_cad == D("5.00")


@pytest.mark.parametrize("bad", ["fractional", "late", "unknown", "unheld"])
def test_invalid_corporate_actions_fail_closed(bad):
    _, a, b, m, limits, _, s = handcase()
    s = replace(s, positions=(Holding(a, 3, D(30), D("37.5")),))
    args = [s, a, "SPLIT", D("0.5"), s.as_of + timedelta(seconds=1), s.as_of, m.fx, limits]
    if bad == "late":
        args[5] = s.as_of + timedelta(seconds=2)
    if bad == "unknown":
        args[2] = "MERGER"
    if bad == "unheld":
        args[1] = b
    with pytest.raises((DataError, ExecutionError)):
        corporate_action(*args)


@pytest.mark.parametrize("case", ["overbuy", "oversell", "withdraw", "fee", "bad_currency"])
def test_no_overdraft_or_shorting(case):
    _, a, _, m, limits, c, s = handcase()
    with pytest.raises((ExecutionError, DataError)):
        if case == "withdraw":
            cash_flow(s, "CAD", D(-1001), s.as_of, m.fx, limits)
        elif case == "bad_currency":
            cash_flow(s, "EUR", D(1), s.as_of, m.fx, limits)
        else:
            costs = replace(c, fixed_fee=D(2000)) if case == "fee" else c
            trade(
                s,
                order(
                    a,
                    "SELL" if case == "oversell" else "BUY",
                    10000 if case == "overbuy" else 1,
                    s.as_of,
                    "10",
                ),
                m,
                s.as_of,
                costs,
                limits,
            )


def test_external_flows_are_not_investment_profit():
    _, _, _, m, limits, _, s = handcase()
    s = cash_flow(s, "USD", D(10), s.as_of, m.fx, limits)
    assert s.net_contributions_cad == D("1012.50")
    assert value_portfolio(s, m, s.as_of, limits).nav_cad == s.net_contributions_cad
    s = cash_flow(s, "USD", D(-5), s.as_of, m.fx, limits)
    assert s.net_contributions_cad == D("1006.25")


def test_caller_decimal_context_does_not_change_core_results():
    _, a, _, m, limits, c, s = handcase()
    expected = trade(s, order(a, "BUY", 7, s.as_of, "10"), m, s.as_of, c, limits)
    with localcontext() as context:
        context.prec = 6
        actual = trade(s, order(a, "BUY", 7, s.as_of, "10"), m, s.as_of, c, limits)
    assert actual == expected


def test_corporate_action_cannot_grant_entitlement_to_same_instant_new_fills():
    _, asset, _, market, limits, costs, state = handcase()
    state, _ = trade(
        state, order(asset, "BUY", 4, state.as_of, "10"), market, state.as_of, costs, limits
    )
    with pytest.raises(ExecutionError, match="precede same-time trades"):
        corporate_action(
            state, asset, "DIVIDEND", D(".50"), state.as_of, state.as_of, market.fx, limits
        )
