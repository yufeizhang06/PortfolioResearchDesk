"""Deterministic USD/CAD fixtures and a separate synthetic CAD history runner."""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from portfolio_research_desk.domain import AssetId, Signal, TradingSession, UniverseSnapshot
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.fx import FXBook, FXRate
from portfolio_research_desk.paper_domain import CADState, Costs, Quote, Sector
from portfolio_research_desk.paper_execution import simulate_plan
from portfolio_research_desk.portfolio_risk import MarketSnapshot, RiskLimits, value_portfolio
from portfolio_research_desk.rebalancing import SignalBundle, propose_rebalance


def example_inputs():
    assets = (
        AssetId("US", "XNAS", "SYN_US_A", "USD"),
        AssetId("CA", "XTSE", "SYN_CA_B", "CAD"),
        AssetId("US", "XNYS", "SYN_US_C", "USD"),
    )
    sessions = tuple(
        TradingSession(
            date(2026, 1, d),
            datetime(2026, 1, d, 14, 30, tzinfo=UTC),
            datetime(2026, 1, d, 21, tzinfo=UTC),
        )
        for d in (5, 6)
    )
    decision = sessions[0].decision_at
    opening = sessions[1].open_at
    sectors = tuple(
        Sector(a, s, sessions[0].open_at, sessions[0].open_at)
        for a, s in zip(assets, ("Technology", "Financials", "Healthcare"), strict=True)
    )

    def snapshot(at, kind, rate):
        return MarketSnapshot(
            tuple(
                Quote(a, at, at, Decimal(p), kind, volume=100000)
                for a, p in zip(assets, ("10.00", "20.00", "25.00"), strict=True)
            ),
            FXBook((FXRate(at, at, Decimal(rate), "synthetic_phase5", True),)),
            sectors,
        )

    market = snapshot(sessions[0].close_at, "close", "1.35")
    execution = snapshot(opening, "open", "1.36")
    universe = UniverseSnapshot(
        "synthetic-cad",
        sessions[0].open_at,
        "user_static",
        assets,
        "synthetic_phase5",
        sessions[0].open_at,
        True,
    )
    bundle = SignalBundle(
        tuple(
            Signal(
                a,
                decision,
                sessions[0].close_at,
                sessions[0].close_at,
                sessions[0].close_at,
                Decimal(3 - i),
            )
            for i, a in enumerate(assets)
        ),
        universe,
        "fixed_synthetic_scores",
    )
    return {
        "bundle": bundle,
        "market": market,
        "sessions": sessions,
        "decision_at": decision,
        "execution_at": opening,
        "review_at": decision + timedelta(minutes=1),
        "execution_market": execution,
    }


@dataclass(frozen=True)
class CADHistoryStep:
    bundle: SignalBundle
    market: MarketSnapshot
    sessions: tuple[TradingSession, ...]
    decision_at: datetime
    execution_market: MarketSnapshot
    valuation_market: MarketSnapshot
    valuation_at: datetime


def run_cad_history(
    initial_state: CADState,
    steps: tuple[CADHistoryStep, ...],
    limits=None,
    costs=None,
    top_k=5,
):
    """Synthetic history uses the identical target, risk, sizing and fill functions.

    No persistent paper state or review authorization can be imported into history.
    This is a software test harness, not real-market PIT certification.
    """
    limits = limits if limits is not None else RiskLimits()
    costs = costs if costs is not None else Costs()
    state, records = initial_state, []
    for i, step in enumerate(steps):
        if any(not q.synthetic for q in step.valuation_market.quotes) or any(
            not r.synthetic for r in step.valuation_market.fx.rates
        ):
            raise DataError("CAD historical valuations must be synthetic.")
        plan = propose_rebalance(
            state,
            step.bundle,
            step.market,
            step.sessions,
            step.decision_at,
            f"cad-history-{i}",
            limits,
            costs,
            top_k,
            mode="backtest",
        )
        state, fills, opening_value = simulate_plan(
            state, plan, step.execution_market, plan.session.open_at
        )
        valuation = value_portfolio(state, step.valuation_market, step.valuation_at, limits)
        state = replace(state, as_of=step.valuation_at)
        records.append(
            {"plan": plan, "fills": fills, "opening": opening_value, "valuation": valuation}
        )
    return state, tuple(records)
