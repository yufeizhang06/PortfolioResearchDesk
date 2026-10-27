"""Long-only Top-K equal targets and close-price integer order proposals."""

from decimal import ROUND_FLOOR

from portfolio_research_desk.backtest_config import BacktestConfig
from portfolio_research_desk.domain import (
    ONE,
    ZERO,
    OrderProposal,
    PortfolioState,
    PriceBar,
    Signal,
    TargetPortfolio,
    fingerprint,
)
from portfolio_research_desk.errors import DataError, ExecutionError


def build_target(signals: tuple[Signal, ...], config: BacktestConfig) -> TargetPortfolio:
    if not signals or len({s.asset for s in signals}) != len(signals):
        raise ExecutionError("A unique, nonempty set of signals is required.")
    if len({s.decision_at for s in signals}) != 1 or config.top_k > len(signals):
        raise ExecutionError("Signals must share one decision time and support top_k.")
    ranked = sorted(signals, key=lambda s: (-s.score, s.asset))[: config.top_k]
    weight = min((ONE - config.cash_buffer) / len(ranked), config.max_position_weight)
    weights = tuple((signal.asset, weight) for signal in ranked)
    return TargetPortfolio(ranked[0].decision_at, weights, ONE - weight * len(ranked))


def propose_orders(
    state: PortfolioState,
    target: TargetPortfolio,
    bars: tuple[PriceBar, ...],
) -> tuple[OrderProposal, ...]:
    """Fix share requests at decision time; tomorrow's open cannot resize them upward."""
    if state.as_of > target.decision_at:
        raise ExecutionError("Cannot propose historical orders from future portfolio state.")
    if len({b.asset for b in bars}) != len(bars):
        raise DataError("Order references must contain one known close per asset.")
    prices = {b.asset: b.close for b in bars}
    if any(b.available_at > target.decision_at for b in bars):
        raise DataError("Order reference price is not available at decision_at.")
    holdings = state.holdings()
    assets = set(holdings) | {asset for asset, _ in target.weights}
    if assets - prices.keys():
        raise DataError("Missing known close for order sizing.")
    if any(asset.currency != state.currency for asset in assets):
        raise ExecutionError("Cross-currency sizing requires an FX implementation.")
    nav = state.cash + sum((prices[a] * q for a, q in holdings.items()), ZERO)
    weights = dict(target.weights)
    orders = []
    for asset in sorted(assets):
        desired = int(
            (nav * weights.get(asset, ZERO) / prices[asset]).to_integral_value(rounding=ROUND_FLOOR)
        )
        delta = desired - holdings.get(asset, 0)
        if delta:
            side = "BUY" if delta > 0 else "SELL"
            order_id = fingerprint([target.decision_at, asset, side])[:24]
            orders.append(
                OrderProposal(order_id, asset, side, abs(delta), target.decision_at, prices[asset])
            )
    return tuple(sorted(orders, key=lambda order: (order.side != "SELL", order.asset)))
