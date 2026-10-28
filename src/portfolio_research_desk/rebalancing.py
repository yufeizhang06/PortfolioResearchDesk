"""Shared, auditable target-to-orders planner for CAD history and paper accounts."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal, InvalidOperation

from portfolio_research_desk.domain import (
    ONE,
    ZERO,
    OrderProposal,
    Signal,
    TargetPortfolio,
    TradingSession,
    UniverseSnapshot,
    fingerprint,
    require_utc,
)
from portfolio_research_desk.errors import DataError, ExecutionError
from portfolio_research_desk.paper_domain import CADState, Costs, accounting
from portfolio_research_desk.paper_execution import CADFill, check_trade_size, trade
from portfolio_research_desk.portfolio import equal_weight_target
from portfolio_research_desk.portfolio_risk import (
    MarketSnapshot,
    RiskLimits,
    Valuation,
    cad_prices,
    value_portfolio,
)


@dataclass(frozen=True)
class SignalBundle:
    signals: tuple[Signal, ...]
    universe: UniverseSnapshot
    source: str
    data_kind: str = "synthetic"
    descriptive_only: bool = False

    def __post_init__(self):
        if (
            not isinstance(self.signals, tuple)
            or any(not isinstance(s, Signal) for s in self.signals)
            or not isinstance(self.universe, UniverseSnapshot)
            or not isinstance(self.source, str)
        ):
            raise DataError(
                "Signals require shared Signal and UniverseSnapshot contracts and a source."
            )

    def validate(self, at, mode):
        if not self.source or self.descriptive_only is not False:
            raise DataError("Descriptive factor results cannot become executable signals.")
        if self.data_kind not in {"synthetic", "paper_observed"}:
            raise DataError("Signals require explicit synthetic or forward paper provenance.")
        if mode == "backtest" and self.data_kind != "synthetic":
            raise DataError(
                "Real signals lack historical PIT certification; CAD history is synthetic-only."
            )
        u = self.universe
        if u.as_of > at or u.available_at is None or u.available_at > at:
            raise DataError("Universe membership is not available at decision time.")
        if self.data_kind == "synthetic" and u.synthetic is not True:
            raise DataError("Synthetic signals require an explicitly synthetic universe.")
        if any(s.asset not in u.assets or s.decision_at != at for s in self.signals):
            raise DataError("Signal must belong to the available universe at this decision.")
        if len({s.asset for s in self.signals}) != len(self.signals):
            raise DataError("Duplicate signals.")


@dataclass(frozen=True)
class RebalancePlan:
    plan_id: str
    mode: str
    data_kind: str
    decision_at: datetime
    session: TradingSession
    state_hash: str
    target: TargetPortfolio
    orders: tuple[OrderProposal, ...]
    limits: RiskLimits
    costs: Costs
    market: MarketSnapshot
    signals: SignalBundle
    before: Valuation
    estimated_after: Valuation
    estimated_fills: tuple[CADFill, ...]
    reasons: tuple[str, ...]


def bundle_from_ml_predictions(records, universe, decision_at, model, *, data_kind):
    """Adapt Phase 4 audit records without reading labels or selecting on test metrics.

    The caller supplies the already selected model and provenance. This adapter
    checks declared timing; it does not certify the supplier's PIT claims.
    """
    require_utc(decision_at)
    signals = []
    try:
        for row in records:
            if row["model"] != model or row["decision_at"] != decision_at:
                continue
            available, fitted = row["available_at"], row["fit_at"]
            require_utc(available)
            require_utc(fitted)
            if fitted > decision_at or available > decision_at:
                raise DataError("ML fit/features are unavailable at paper decision time.")
            known = max(available, fitted)
            signals.append(
                Signal(
                    row["asset"],
                    decision_at,
                    min(available, fitted),
                    known,
                    known,
                    Decimal(str(row["score"])),
                )
            )
    except (KeyError, TypeError, InvalidOperation) as exc:
        raise DataError("Invalid Phase 4 prediction record.") from exc
    if not signals:
        raise DataError("No selected-model predictions for the requested decision.")
    bundle = SignalBundle(tuple(signals), universe, f"ml:{model}", data_kind)
    bundle.validate(decision_at, "paper")
    return bundle


@accounting
def constrained_target(bundle, at, top_k, limits, market):
    if not bundle.signals:
        return TargetPortfolio(at, (), ONE)
    top_k = min(top_k, limits.max_positions, len(bundle.signals))
    base = equal_weight_target(
        bundle.signals, top_k, limits.cash_buffer, limits.max_position_weight
    )
    sectors = market.known_sectors([a for a, _ in base.weights], at)
    counts = {}
    for asset, _ in base.weights:
        counts[sectors[asset]] = counts.get(sectors[asset], 0) + 1
    weights = tuple(
        (a, min(w, limits.max_sector_weight / counts[sectors[a]])) for a, w in base.weights
    )
    return TargetPortfolio(at, weights, ONE - sum((w for _, w in weights), ZERO))


@accounting
def propose_rebalance(
    state: CADState,
    bundle: SignalBundle,
    market: MarketSnapshot,
    sessions: tuple[TradingSession, ...],
    decision_at: datetime,
    plan_id: str,
    limits=None,
    costs=None,
    top_k=5,
    target: TargetPortfolio | None = None,
    mode="paper",
):
    require_utc(decision_at)
    limits = limits if limits is not None else RiskLimits()
    costs = costs if costs is not None else Costs()
    if not isinstance(bundle, SignalBundle) or not isinstance(market, MarketSnapshot):
        raise DataError("Proposal requires a SignalBundle and MarketSnapshot.")
    if not isinstance(limits, RiskLimits) or not isinstance(costs, Costs):
        raise DataError("Proposal requires validated risk limits and costs.")
    if not isinstance(sessions, tuple) or any(not isinstance(s, TradingSession) for s in sessions):
        raise DataError("Proposal requires an explicit tuple of TradingSession records.")
    if target is not None and not isinstance(target, TargetPortfolio):
        raise DataError("Explicit target must be a TargetPortfolio.")
    if mode not in {"paper", "backtest"} or not isinstance(plan_id, str) or not plan_id:
        raise ExecutionError("Plan requires an ID and explicit paper/backtest mode.")
    if type(top_k) is not int or top_k < 1:
        raise DataError("top_k must be a positive integer.")
    bundle.validate(decision_at, mode)
    if tuple(sorted(sessions, key=lambda s: s.open_at)) != sessions or len(set(sessions)) != len(
        sessions
    ):
        raise DataError("Session manifest must be sorted and unique.")
    if any(a.close_at >= b.open_at for a, b in zip(sessions, sessions[1:], strict=False)):
        raise DataError("Session manifest overlaps.")
    previous = [s for s in sessions if s.close_at < decision_at]
    future = [s for s in sessions if s.open_at > decision_at]
    if not previous or not future or any(s.open_at <= decision_at <= s.close_at for s in sessions):
        raise ExecutionError("Decision must follow a manifest close and precede a next session.")
    session = future[0]
    if session.session_date <= decision_at.date():
        raise ExecutionError("Same-day simulated execution is prohibited.")
    if bundle.data_kind == "synthetic" and (
        any(not q.synthetic for q in market.quotes) or any(not r.synthetic for r in market.fx.rates)
    ):
        raise DataError("Cannot mix real data into a synthetic plan.")
    before = value_portfolio(state, market, decision_at, limits)
    if before.nav_cad <= 0:
        raise ExecutionError("A funded positive-NAV account is required.")
    target = (
        target
        if target is not None
        else constrained_target(bundle, decision_at, top_k, limits, market)
    )
    if target.decision_at != decision_at or any(
        a not in bundle.universe.assets for a, _ in target.weights
    ):
        raise DataError("Target timestamp/universe mismatch.")
    active = [(a, w) for a, w in target.weights if w]
    sectors = market.known_sectors([a for a, _ in active], decision_at)
    exposure = {}
    for a, w in active:
        exposure[sectors[a]] = exposure.get(sectors[a], ZERO) + w
    if (
        len(active) > limits.max_positions
        or target.cash_weight < limits.cash_buffer
        or any(w > limits.max_position_weight for _, w in active)
        or any(w > limits.max_sector_weight for w in exposure.values())
    ):
        raise ExecutionError("Target violates configured risk limits.")
    prices = cad_prices(market, decision_at, limits)
    quotes = market.known_quotes(decision_at, limits)
    holdings = state.holdings()
    weights = dict(target.weights)
    assets = set(holdings) | {a for a, _ in active}
    if assets - prices.keys():
        raise DataError("Missing decision price for target/holding.")
    requests = []
    for asset in sorted(assets):
        desired = int(
            (before.nav_cad * weights.get(asset, ZERO) / prices[asset]).to_integral_value(
                rounding=ROUND_FLOOR
            )
        )
        delta = desired - (holdings[asset].quantity if asset in holdings else 0)
        if delta:
            requests.append((asset, "BUY" if delta > 0 else "SELL", abs(delta)))
    orders, fills, reasons, current, turnover = [], [], [], state, ZERO
    for asset, side, requested in sorted(requests, key=lambda r: (r[1] != "SELL", r[0])):

        def candidate(quantity, asset=asset, side=side, turnover=turnover, current=current):
            check_trade_size(quantity, prices[asset] * quantity, before.nav_cad, turnover, limits)
            order = OrderProposal(
                fingerprint([plan_id, asset, side])[:32],
                asset,
                side,
                quantity,
                decision_at,
                quotes[asset].price,
            )
            result, fill = trade(current, order, market, decision_at, costs, limits)
            if side == "BUY" and value_portfolio(result, market, decision_at, limits).violations:
                raise ExecutionError("Buy would exceed cash/concentration limits.")
            return order, result, fill

        # Minimum trade constraints are not monotone near zero: search upper range,
        # then apply the minimum once to the feasible maximum.
        high = min(
            requested,
            limits.max_order_shares,
            quotes[asset].volume if quotes[asset].tradable else 0,
            int(
                (before.nav_cad * limits.max_trade_weight / prices[asset]).to_integral_value(
                    rounding=ROUND_FLOOR
                )
            ),
            int(
                (
                    (before.nav_cad * limits.max_turnover - turnover) / prices[asset]
                ).to_integral_value(rounding=ROUND_FLOOR)
            ),
        )
        low = 0
        minimum = int(
            (limits.min_trade_cad / prices[asset]).to_integral_value(rounding="ROUND_CEILING")
        )
        if side == "SELL":
            # Sale proceeds can first become sufficient to pay a fixed fee at
            # larger quantities. Smaller failures cannot bound the upper range.
            try:
                if high and high >= minimum:
                    candidate(high)
                    low = high
            except ExecutionError:
                pass
        else:
            while low < high:
                mid = (low + high + 1) // 2
                if mid < minimum:
                    low = mid
                    continue
                try:
                    candidate(mid)
                    low = mid
                except ExecutionError:
                    high = mid - 1
        if low and low >= minimum:
            order, current, fill = candidate(low)
            orders.append(order)
            fills.append(fill)
            turnover += prices[asset] * low
        if low < requested or low < minimum:
            reasons.append(
                f"{asset.symbol}: requested {requested}; planned {low if low >= minimum else 0}; "
                "integer/cash/risk/trade limits"
            )
    after = value_portfolio(current, market, decision_at, limits)
    if after.violations:
        raise ExecutionError(
            "No feasible rebalance under trade limits: " + ", ".join(after.violations)
        )
    if target.cash_weight > limits.cash_buffer:
        reasons.append("Unallocated target capital retained as cash under concentration limits.")
    return RebalancePlan(
        plan_id,
        mode,
        bundle.data_kind,
        decision_at,
        session,
        fingerprint(state),
        target,
        tuple(orders),
        limits,
        costs,
        market,
        bundle,
        before,
        after,
        tuple(fills),
        tuple(reasons),
    )
