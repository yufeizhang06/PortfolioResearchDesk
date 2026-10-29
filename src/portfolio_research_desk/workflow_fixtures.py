"""Adapters for a shared, explicitly synthetic universe-to-CAD-paper demonstration."""

from decimal import Decimal

from portfolio_research_desk.domain import jsonable
from portfolio_research_desk.fx import FXBook, FXRate
from portfolio_research_desk.market_data import load_backtest_dataset
from portfolio_research_desk.paper_domain import Quote, Sector
from portfolio_research_desk.portfolio_risk import MarketSnapshot
from portfolio_research_desk.rebalancing import SignalBundle
from portfolio_research_desk.signals import momentum_signals
from portfolio_research_desk.universe import custom_universe


def identity(asset):
    return ":".join((asset.market, asset.exchange, asset.symbol, asset.currency))


def snapshot_document(market, at, purpose, bundle=None, sessions=()):
    """Emit readable input with no Python class tags and no implicit current times."""
    value = {
        "schema_version": 6,
        "purpose": purpose,
        "as_of": at.isoformat(),
        "data_kind": "synthetic",
        "source": "synthetic_delivery_fixture",
        "prices": [
            {
                "asset": identity(q.asset),
                "observed_at": q.observed_at.isoformat(),
                "available_at": q.available_at.isoformat(),
                "price": str(q.price),
                "kind": q.kind,
                "tradable": q.tradable,
                "volume": q.volume,
                "adjusted": q.adjusted,
            }
            for q in market.quotes
        ],
        "sectors": [
            {
                "asset": identity(s.asset),
                "name": s.name,
                "effective_at": s.effective_at.isoformat(),
                "available_at": s.available_at.isoformat(),
            }
            for s in market.sectors
        ],
        "fx": [
            {
                "observed_at": r.observed_at.isoformat(),
                "available_at": r.available_at.isoformat(),
                "cad_per_usd": str(r.cad_per_usd),
            }
            for r in market.fx.rates
        ],
    }
    if bundle is not None:
        u = bundle.universe
        value["universe"] = {
            "universe_id": u.universe_id,
            "as_of": u.as_of.isoformat(),
            "available_at": u.available_at.isoformat(),
            "membership_type": u.membership_type,
            "assets": [identity(a) for a in u.assets],
        }
        value["signals"] = [
            {
                "asset": identity(s.asset),
                "score": str(s.score),
                "observation_start": s.observation_start.isoformat(),
                "observation_end": s.observation_end.isoformat(),
                "available_at": s.available_at.isoformat(),
            }
            for s in bundle.signals
        ]
        value["sessions"] = [
            {
                "date": s.session_date.isoformat(),
                "open_at": s.open_at.isoformat(),
                "close_at": s.close_at.isoformat(),
            }
            for s in sessions
        ]
    return jsonable(value)


def delivery_inputs():
    dataset = load_backtest_dataset()
    decision_session, execution_session = dataset.sessions[2:4]
    assets = tuple(sorted({b.asset for b in dataset.bars}))
    universe = custom_universe(assets, dataset.sessions[0].open_at, True)
    signals = momentum_signals(dataset.bars, assets, decision_session.decision_at, 1)
    bundle = SignalBundle(signals, universe, "synthetic_momentum_1_session")
    sectors = tuple(
        Sector(a, name, universe.as_of, universe.as_of)
        for a, name in zip(assets, ("Technology", "Financials", "Healthcare"), strict=True)
    )

    def market(session, opening, rate):
        at = session.open_at if opening else session.close_at
        bars = tuple(b for b in dataset.bars if b.session_date == session.session_date)
        quotes = tuple(
            Quote(
                b.asset,
                at,
                at if opening else b.available_at,
                b.open if opening else b.close,
                "open" if opening else "close",
                b.tradable,
                b.volume,
                source="synthetic_v1",
            )
            for b in bars
        )
        return MarketSnapshot(
            quotes, FXBook((FXRate(at, at, Decimal(rate), "synthetic_delivery_fx", True),)), sectors
        )

    decision = market(decision_session, False, "1.35")
    opening = market(execution_session, True, "1.35")
    closing = market(execution_session, False, "1.30")
    return {
        "dataset": dataset,
        "bundle": bundle,
        "decision": decision,
        "opening": opening,
        "closing": closing,
        "sessions": dataset.sessions,
        "decision_at": decision_session.decision_at,
        "execution_at": execution_session.open_at,
        "valuation_at": execution_session.decision_at,
    }


def paper_documents():
    x = delivery_inputs()
    return {
        "decision": snapshot_document(
            x["decision"], x["decision_at"], "decision", x["bundle"], x["sessions"]
        ),
        "opening": snapshot_document(x["opening"], x["execution_at"], "execution"),
        "closing": snapshot_document(x["closing"], x["valuation_at"], "valuation"),
    }
