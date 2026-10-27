"""Deterministic daily event loop: next open execution, close valuation, decision."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Context, Decimal, localcontext

from portfolio_research_desk.backtest_config import BacktestConfig
from portfolio_research_desk.domain import (
    ONE,
    ZERO,
    EquityPoint,
    Fill,
    OrderOutcome,
    OrderProposal,
    PortfolioState,
    PositionValue,
    Signal,
    TargetPortfolio,
    UniverseSnapshot,
    fingerprint,
)
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.execution import execute_orders
from portfolio_research_desk.market_data import (
    MarketDataset,
    load_backtest_dataset,
    validate_dataset,
)
from portfolio_research_desk.portfolio import build_target, propose_orders
from portfolio_research_desk.signals import momentum_signals


@dataclass(frozen=True)
class DecisionRecord:
    decision_at: datetime
    signals: tuple[Signal, ...]
    target: TargetPortfolio
    proposed_orders: tuple[OrderProposal, ...]


@dataclass(frozen=True)
class BacktestResult:
    config: BacktestConfig
    universe: UniverseSnapshot
    data_hash: str
    equity: tuple[EquityPoint, ...]
    decisions: tuple[DecisionRecord, ...]
    orders: tuple[OrderOutcome, ...]
    fills: tuple[Fill, ...]
    final_state: PortfolioState
    metrics: dict[str, Decimal | int | None]
    warnings: tuple[str, ...]
    dataset_snapshot: MarketDataset


SignalProvider = Callable[[datetime], tuple[Signal, ...] | None]


def run_backtest(
    config: BacktestConfig,
    dataset: MarketDataset | None = None,
    signal_provider: SignalProvider | None = None,
) -> BacktestResult:
    """Run momentum or injected audited signals through the same execution engine.

    A provider returns None to hold, an empty tuple to target cash, or a complete
    signal panel to rebalance. Fitting remains outside the execution engine.
    """
    # Prevent a caller's Decimal context from silently changing an experiment.
    with localcontext(Context(prec=28)):
        return _run(
            config, dataset if dataset is not None else load_backtest_dataset(), signal_provider
        )


def _run(
    config: BacktestConfig, dataset: MarketDataset, signal_provider: SignalProvider | None
) -> BacktestResult:
    validate_dataset(dataset)
    if config.lookback_sessions >= len(dataset.sessions) - 1:
        raise DataError(
            "Insufficient history: need lookback + 2 explicit sessions for a possible fill."
        )
    available = {b.asset.symbol: b.asset for b in dataset.bars}
    if set(config.symbols) - available.keys():
        raise DataError("Custom universe contains symbols absent from the synthetic dataset.")
    assets = tuple(available[symbol] for symbol in config.symbols)
    first = dataset.sessions[0]
    universe = UniverseSnapshot(
        f"custom-{fingerprint(assets)[:16]}", first.open_at, "user_static", assets, "user_config"
    )
    bars = tuple(b for b in dataset.bars if b.asset in assets)
    state = PortfolioState(first.open_at, config.initial_cash)
    pending: tuple[OrderProposal, ...] = ()
    equity: list[EquityPoint] = []
    decisions = []
    fills: list[Fill] = []
    orders: list[OrderOutcome] = []
    fees, slippage = ZERO, ZERO
    warnings = [
        "SYNTHETIC USD-only verification; not historical market or OOS investment evidence.",
        "user_static universe: no historical membership, delisting or survivorship-bias coverage.",
        "Explicit fixture sessions and assumed opening liquidity; no verified exchange calendar.",
        "No splits/dividends/FX/interest; corporate actions must be declared none.",
        "No ML, Walk-Forward training or final holdout evaluation in Phase 1.",
        "Cash benchmark: zero interest. Annualized return/volatility/Sharpe unavailable.",
    ]
    if signal_provider is not None:
        warnings[4] = (
            "Injected research signals; see caller's fold audit and synthetic limitations."
        )
    for index, session in enumerate(dataset.sessions):
        current = tuple(b for b in bars if b.session_date == session.session_date)
        executed = execute_orders(state, pending, current, session, config)
        state = executed.state
        fills.extend(executed.fills)
        orders.extend(executed.orders)
        fees += sum((f.commission for f in executed.fills), ZERO)
        slippage += sum((f.slippage_cost for f in executed.fills), ZERO)
        if any(b.available_at > session.decision_at for b in current):
            raise DataError(
                "Close valuation input is not available at the scheduled decision time."
            )
        marks = {b.asset: b.close for b in current}
        nav = state.cash + sum((marks[p.asset] * p.quantity for p in state.positions), ZERO)
        positions = tuple(
            PositionValue(
                p.asset,
                p.quantity,
                marks[p.asset],
                marks[p.asset] * p.quantity,
                marks[p.asset] * p.quantity / nav,
            )
            for p in state.positions
        )
        equity.append(
            EquityPoint(
                session.session_date,
                session.decision_at,
                state.cash,
                nav,
                positions,
                fees,
                slippage,
                config.initial_cash,
            )
        )
        if any(p.weight > config.max_position_weight for p in positions):
            warnings.append(
                f"Close-price drift exceeded target cap on {session.session_date}; "
                "execution caps do not guarantee intraday weights."
            )
        state = PortfolioState(session.decision_at, state.cash, state.positions)
        pending = ()
        if index >= config.lookback_sessions:
            signals = (
                momentum_signals(bars, assets, session.decision_at, config.lookback_sessions)
                if signal_provider is None
                else signal_provider(session.decision_at)
            )
            if signals is None:
                continue
            if signals and (
                set(s.asset for s in signals) != set(assets)
                or any(s.decision_at != session.decision_at for s in signals)
            ):
                raise DataError("Injected signals require the current complete configured panel.")
            target = (
                build_target(signals, config)
                if signals
                else TargetPortfolio(session.decision_at, (), ONE)
            )
            pending = propose_orders(state, target, current)
            decisions.append(DecisionRecord(session.decision_at, signals, target, pending))
    final_cancel = execute_orders(state, pending, (), None, config)
    orders.extend(final_cancel.orders)
    peak, drawdown = config.initial_cash, ZERO
    for point in equity:
        peak = max(peak, point.nav)
        drawdown = max(drawdown, ONE - point.nav / peak)
    metrics = {
        "initial_nav": config.initial_cash,
        "ending_nav": equity[-1].nav,
        "cumulative_return": equity[-1].nav / config.initial_cash - ONE,
        "max_drawdown": drawdown,
        "total_commission": fees,
        "total_slippage_cost": slippage,
        "fill_count": len(fills),
        "cancelled_order_count": sum(o.status == "CANCELLED" for o in orders),
        "traded_notional_over_initial_capital": sum((f.raw_price * f.quantity for f in fills), ZERO)
        / config.initial_cash,
        "cash_benchmark_return": ZERO,
        "annualized_return": None,
        "annualized_volatility": None,
        "sharpe": None,
    }
    return BacktestResult(
        config,
        universe,
        dataset.data_hash,
        tuple(equity),
        tuple(decisions),
        tuple(orders),
        tuple(fills),
        state,
        metrics,
        tuple(warnings),
        dataset,
    )
