"""Next-session simulation with conservative costs and immutable accounting."""

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from portfolio_research_desk.backtest_config import BacktestConfig
from portfolio_research_desk.domain import (
    BPS,
    CENT,
    ONE,
    ZERO,
    AssetId,
    Fill,
    OrderOutcome,
    OrderProposal,
    PortfolioState,
    Position,
    PriceBar,
    TradingSession,
)
from portfolio_research_desk.errors import ExecutionError


@dataclass(frozen=True)
class ExecutionResult:
    state: PortfolioState
    fills: tuple[Fill, ...]
    orders: tuple[OrderOutcome, ...]


def commission(quantity: int, price: Decimal, config: BacktestConfig) -> Decimal:
    if quantity == 0:
        return ZERO
    return (config.fixed_fee + quantity * price * config.commission_bps / BPS).quantize(
        CENT,
        rounding=ROUND_CEILING,
    )


def _within_limits(
    cash: Decimal,
    holdings: dict[AssetId, int],
    prices: dict[AssetId, Decimal],
    config: BacktestConfig,
) -> bool:
    nav = cash + sum((prices[asset] * quantity for asset, quantity in holdings.items()), ZERO)
    return (
        nav > 0
        and cash >= 0
        and cash >= config.cash_buffer * nav
        and all(
            quantity * prices[asset] <= config.max_position_weight * nav
            for asset, quantity in holdings.items()
        )
    )


def execute_orders(
    state: PortfolioState,
    orders: tuple[OrderProposal, ...],
    bars: tuple[PriceBar, ...],
    session: TradingSession | None,
    config: BacktestConfig,
) -> ExecutionResult:
    """Execute at the caller's next explicit session; requests may only be reduced.

    The engine supplies the immediate next calendar entry. A missing held open
    cancels the entire batch: no stale marks are invented for execution risk.
    Unresolvable inherited exposure from a price gap fails closed.
    """
    if len({order.order_id for order in orders}) != len(orders):
        raise ExecutionError("Duplicate order IDs in execution batch.")
    if not orders:
        return ExecutionResult(state, (), ())
    if session is None:
        return ExecutionResult(
            state,
            (),
            tuple(OrderOutcome(o, None, 0, "CANCELLED", "NO_NEXT_SESSION") for o in orders),
        )
    if state.as_of > session.open_at:
        raise ExecutionError("Portfolio state is from after the execution time.")
    for order in orders:
        if (
            not order.decision_at < session.open_at
            or order.decision_at.date() >= session.session_date
        ):
            raise ExecutionError(
                "Execution must follow the decision on a later session, never same close."
            )
        if order.asset.currency != state.currency:
            raise ExecutionError("Order currency requires FX; Phase 1 is USD-only.")
    if any(b.session_date != session.session_date or b.open_at != session.open_at for b in bars):
        raise ExecutionError("Execution quotes do not match the supplied session.")
    if len({b.asset for b in bars}) != len(bars):
        raise ExecutionError("Duplicate opening quotes.")
    quotes = {b.asset: b for b in bars}
    prices = {b.asset: b.open for b in bars if b.open is not None and b.tradable}
    holdings = state.holdings()
    if holdings.keys() - prices.keys():
        return ExecutionResult(
            state,
            (),
            tuple(
                OrderOutcome(o, session.open_at, 0, "CANCELLED", "UNAVAILABLE_HELD_OPEN")
                for o in orders
            ),
        )
    cash = state.cash
    fills = []
    outcomes = []
    for order in sorted(orders, key=lambda o: (o.side != "SELL", o.asset)):
        quote = quotes.get(order.asset)
        if quote is None or quote.open is None or not quote.tradable:
            outcomes.append(
                OrderOutcome(order, session.open_at, 0, "CANCELLED", "NO_TRADABLE_OPEN")
            )
            continue
        raw = quote.open
        direction = ONE if order.side == "BUY" else -ONE
        price = (raw * (ONE + direction * config.slippage_bps / BPS)).quantize(
            CENT,
            rounding=ROUND_CEILING if order.side == "BUY" else ROUND_FLOOR,
        )
        if price <= 0:
            outcomes.append(
                OrderOutcome(order, session.open_at, 0, "CANCELLED", "NONPOSITIVE_FILL_PRICE")
            )
            continue
        quantity = order.quantity
        if order.side == "SELL":
            if quantity > holdings.get(order.asset, 0):
                raise ExecutionError("Sell quantity exceeds held integer shares.")
            if cash + quantity * price - commission(quantity, price, config) < 0:
                outcomes.append(
                    OrderOutcome(order, session.open_at, 0, "CANCELLED", "UNAFFORDABLE_SELL_FEE")
                )
                continue
        else:
            if not _within_limits(cash, holdings, prices, config):
                raise ExecutionError(
                    "Open-price gap makes current cash/weight limits infeasible; refusing buys."
                )
            # Feasibility is monotone in buy quantity (costs only reduce NAV).
            low, high = 0, quantity
            while low < high:
                candidate = (low + high + 1) // 2
                proposed = dict(holdings)
                proposed[order.asset] = proposed.get(order.asset, 0) + candidate
                next_cash = cash - candidate * price - commission(candidate, price, config)
                if _within_limits(next_cash, proposed, prices, config):
                    low = candidate
                else:
                    high = candidate - 1
            quantity = low
        if quantity == 0:
            outcomes.append(
                OrderOutcome(order, session.open_at, 0, "CANCELLED", "CASH_OR_WEIGHT_LIMIT")
            )
            continue
        fee = commission(quantity, price, config)
        cash -= direction * quantity * price + fee
        holdings[order.asset] = holdings.get(order.asset, 0) + int(direction) * quantity
        if holdings[order.asset] == 0:
            del holdings[order.asset]
        fills.append(
            Fill(
                order.order_id,
                order.asset,
                order.side,
                quantity,
                order.decision_at,
                session.open_at,
                raw,
                price,
                fee,
                abs(price - raw) * quantity,
            )
        )
        outcomes.append(
            OrderOutcome(
                order,
                session.open_at,
                quantity,
                "FILLED" if quantity == order.quantity else "PARTIAL",
                "SIMULATED" if quantity == order.quantity else "CASH_OR_WEIGHT_LIMIT",
            )
        )
    if fills and not _within_limits(cash, holdings, prices, config):
        raise ExecutionError(
            "Post-execution cash/weight constraints are infeasible after the opening gap/costs."
        )
    updated = PortfolioState(
        session.open_at, cash, tuple(Position(a, q) for a, q in sorted(holdings.items()))
    )
    # The ledger movement must equal signed fill notional plus commissions.
    expected_cash = state.cash - sum(
        ((1 if f.side == "BUY" else -1) * f.quantity * f.price + f.commission for f in fills), ZERO
    )
    if updated.cash != expected_cash:
        raise ExecutionError("Execution cash ledger does not reconcile.")
    return ExecutionResult(updated, tuple(fills), tuple(outcomes))
