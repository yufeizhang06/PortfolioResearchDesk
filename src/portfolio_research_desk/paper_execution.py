"""Pure CAD simulation and ledger movements; no broker integration."""

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from portfolio_research_desk.domain import (
    BPS,
    CENT,
    ONE,
    ZERO,
    OrderProposal,
    fingerprint,
    require_utc,
)
from portfolio_research_desk.errors import ExecutionError
from portfolio_research_desk.fx import Conversion, FXRate, fund_usd, rate_for, sell_usd
from portfolio_research_desk.paper_domain import Holding, accounting, money, number, supported
from portfolio_research_desk.portfolio_risk import value_portfolio


@dataclass(frozen=True)
class CADFill:
    order: OrderProposal
    execution_at: datetime
    raw_price: Decimal
    price: Decimal
    commission_local: Decimal
    fx_rate: FXRate | None
    conversion: Conversion | None
    slippage_cad: Decimal


@accounting
def trade(state, order, market, at, costs, limits):
    """Apply one exact integer request; caller checks batch risk and review policy."""
    require_utc(at)
    quotes = market.known_quotes(at, limits)
    q = quotes.get(order.asset)
    if q is None or not q.tradable or q.volume < order.quantity:
        raise ExecutionError("Missing tradable/liquid quote; no simulated fill.")
    if abs(q.price / order.reference_price - ONE) > limits.max_price_deviation:
        raise ExecutionError("Abnormal execution price deviation from reviewed reference.")
    sign = ONE if order.side == "BUY" else -ONE
    price = (q.price * (ONE + sign * costs.slippage_bps / BPS)).quantize(
        CENT, rounding=ROUND_CEILING if order.side == "BUY" else ROUND_FLOOR
    )
    if price <= 0:
        raise ExecutionError("Nonpositive simulated fill price.")
    gross = price * order.quantity
    fee = (costs.fixed_fee + gross * costs.commission_bps / BPS).quantize(
        CENT, rounding=ROUND_CEILING
    )
    rate = rate_for(order.asset.currency, market.fx, at, limits.fx_age)
    balances = state.balances()
    holdings = state.holdings()
    old = holdings.get(order.asset)
    if order.side == "SELL" and (old is None or old.quantity < order.quantity):
        raise ExecutionError("Sell exceeds held shares; short sales prohibited.")
    balances[order.asset.currency] -= sign * gross + fee
    conversion = None
    fx_cost = ZERO
    if balances["USD"] < 0:
        conversion = fund_usd(-balances["USD"], market.fx, at, costs.fx_fee_bps, limits.fx_age)
        balances["USD"] += conversion.destination_amount
        balances["CAD"] -= conversion.source_amount + conversion.fee_cad
        fx_cost = conversion.fee_cad + conversion.rounding_cad
    if any(amount < 0 for amount in balances.values()):
        raise ExecutionError("Insufficient currency cash after fees and FX; overdraft prohibited.")
    realized = state.realized_pnl_cad
    if order.side == "BUY":
        holdings[order.asset] = Holding(
            order.asset,
            (old.quantity if old else 0) + order.quantity,
            (old.cost_local if old else ZERO) + gross + fee,
            (old.cost_cad if old else ZERO) + (gross + fee) * rate + fx_cost,
        )
    else:
        removed_local = (
            old.cost_local
            if order.quantity == old.quantity
            else old.cost_local * order.quantity / old.quantity
        )
        removed_cad = (
            old.cost_cad
            if order.quantity == old.quantity
            else old.cost_cad * order.quantity / old.quantity
        )
        realized += (gross - fee) * rate - fx_cost - removed_cad
        if old.quantity == order.quantity:
            del holdings[order.asset]
        else:
            holdings[order.asset] = Holding(
                order.asset,
                old.quantity - order.quantity,
                old.cost_local - removed_local,
                old.cost_cad - removed_cad,
            )
    slippage = abs(price - q.price) * order.quantity * rate
    updated = replace(
        state,
        as_of=at,
        cash=tuple(sorted(balances.items())),
        positions=tuple(holdings[a] for a in sorted(holdings)),
        commission_cad=state.commission_cad + fee * rate,
        fx_cost_cad=state.fx_cost_cad + fx_cost,
        slippage_cad=state.slippage_cad + slippage,
        realized_pnl_cad=realized,
    )
    before = value_portfolio(state, market, at, limits).nav_cad
    after = value_portfolio(updated, market, at, limits).nav_cad
    if abs(before - after - fee * rate - fx_cost - slippage) > ONE.scaleb(-35):
        raise ExecutionError("CAD accounting identity failed across simulated trade.")
    fx = market.fx.at(at, limits.fx_age) if order.asset.currency == "USD" else None
    return updated, CADFill(order, at, q.price, price, fee, fx, conversion, slippage)


@accounting
def simulate_plan(state, plan, market, execution_at):
    """Exact reviewed batch. Failure leaves the original state wholly unchanged."""
    require_utc(execution_at)
    if plan.state_hash != fingerprint(state):
        raise ExecutionError("Stale plan: account changed after proposal.")
    if execution_at != plan.session.open_at or not plan.decision_at < execution_at:
        raise ExecutionError("Execution must be the planned next session open.")
    if plan.decision_at.date() >= execution_at.date():
        raise ExecutionError("Same-day decision and execution prohibited.")
    quotes = market.known_quotes(execution_at, plan.limits)
    required = set(state.holdings()) | {o.asset for o in plan.orders}
    if any(
        a not in quotes or quotes[a].kind != "open" or quotes[a].observed_at != execution_at
        for a in required
    ):
        raise ExecutionError("Every held/ordered asset requires this session's raw opening quote.")
    if plan.mode == "backtest" and plan.data_kind != "synthetic":
        raise ExecutionError("Historical CAD execution is synthetic-only; real PIT not certified.")
    if plan.data_kind == "synthetic" and (
        any(not q.synthetic for q in market.quotes) or any(not r.synthetic for r in market.fx.rates)
    ):
        raise ExecutionError("Synthetic plans cannot mix real execution prices or FX in any mode.")
    initial_nav = value_portfolio(state, market, execution_at, plan.limits).nav_cad
    current, fills, turnover = state, [], ZERO
    if len({o.order_id for o in plan.orders}) != len(plan.orders):
        raise ExecutionError("Duplicate order in plan.")
    for order in plan.orders:
        if order.decision_at != plan.decision_at:
            raise ExecutionError("Order timestamp differs from reviewed decision.")
        cad_notional = (
            order.quantity
            * quotes[order.asset].price
            * rate_for(order.asset.currency, market.fx, execution_at, plan.limits.fx_age)
        )
        check_trade_size(order.quantity, cad_notional, initial_nav, turnover, plan.limits)
        turnover += cad_notional
        current, fill = trade(current, order, market, execution_at, plan.costs, plan.limits)
        fills.append(fill)
    after = value_portfolio(current, market, execution_at, plan.limits)
    if after.violations:
        raise ExecutionError("Post-execution risk violation: " + ", ".join(after.violations))
    return replace(current, as_of=execution_at), tuple(fills), after


def check_trade_size(quantity, notional, nav, turnover, limits):
    if (
        quantity > limits.max_order_shares
        or notional < limits.min_trade_cad
        or notional > nav * limits.max_trade_weight
        or turnover + notional > nav * limits.max_turnover
    ):
        raise ExecutionError("Trade violates share/notional/minimum/turnover limits.")


@accounting
def convert_cash(state, source, amount, book, at, costs, limits):
    require_utc(at)
    if state.as_of > at:
        raise ExecutionError("Cash conversion cannot precede account state.")
    if not isinstance(source, str) or source not in {"CAD", "USD"}:
        raise ExecutionError("Conversion supports CAD and USD only.")
    # CAD source uses exact desired destination USD cents; USD source is USD sold.
    conversion = (fund_usd if source == "CAD" else sell_usd)(
        amount, book, at, costs.fx_fee_bps, limits.fx_age
    )
    balances = state.balances()
    balances[source] -= conversion.source_amount
    if source == "CAD":
        balances["CAD"] -= conversion.fee_cad
    balances[conversion.destination_currency] += conversion.destination_amount
    if any(b < 0 for b in balances.values()):
        raise ExecutionError("Insufficient cash for conversion and fee.")
    return replace(
        state,
        as_of=at,
        cash=tuple(sorted(balances.items())),
        fx_cost_cad=state.fx_cost_cad + conversion.fee_cad + conversion.rounding_cad,
    ), conversion


@accounting
def cash_flow(state, currency, amount, at, book, limits):
    """Signed external flow; independent from investment income and trading P&L."""
    require_utc(at)
    if not isinstance(currency, str) or currency not in {"CAD", "USD"} or state.as_of > at:
        raise ExecutionError("Invalid currency or backdated cash flow.")

    number(amount, "signed cash flow", -Decimal("1e12"), Decimal("1e12"))
    money(abs(amount), "cash flow", positive=True)
    balances = state.balances()
    balances[currency] += amount
    if balances[currency] < 0:
        raise ExecutionError("Withdrawal exceeds currency cash.")
    contribution = amount * rate_for(currency, book, at, limits.fx_age)
    return replace(
        state,
        as_of=at,
        cash=tuple(sorted(balances.items())),
        net_contributions_cad=state.net_contributions_cad + contribution,
    )


@accounting
def corporate_action(state, asset, kind, amount, effective_at, available_at, book, limits):
    """Apply at effective time before later trades; event ID enforces exactly once."""
    require_utc(effective_at)
    require_utc(available_at)
    supported(asset)
    if not isinstance(kind, str):
        raise ExecutionError("Corporate action type must be an explicit string.")
    if state.as_of >= effective_at or available_at > effective_at:
        raise ExecutionError(
            "Corporate actions must follow prior state and precede same-time trades; "
            "late/backdated actions require historical reconstruction."
        )
    holdings = state.holdings()
    old = holdings.get(asset)
    if old is None:
        raise ExecutionError("Corporate action requires a held asset.")
    if kind == "SPLIT":
        number(amount, "split ratio", CENT)
        quantity = old.quantity * amount
        if quantity != quantity.to_integral_value() or quantity < 1:
            raise ExecutionError("Fractional split requires cash-in-lieu; not supported.")
        holdings[asset] = replace(old, quantity=int(quantity))
        return replace(
            state, as_of=effective_at, positions=tuple(holdings[a] for a in sorted(holdings))
        )
    if kind != "DIVIDEND":
        raise ExecutionError("Unknown corporate action.")
    money(amount, "dividend per share", positive=True)
    cash = state.balances()
    cash[asset.currency] += old.quantity * amount
    income = old.quantity * amount * rate_for(asset.currency, book, effective_at, limits.fx_age)
    return replace(
        state,
        as_of=effective_at,
        cash=tuple(sorted(cash.items())),
        dividends_cad=state.dividends_cad + income,
    )
