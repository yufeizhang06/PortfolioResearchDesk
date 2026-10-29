"""Readable, strict JSON transport for Paper services; no execution/accounting logic."""

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from portfolio_research_desk.domain import (
    AssetId,
    Signal,
    TargetPortfolio,
    TradingSession,
    UniverseSnapshot,
    require_utc,
)
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.fx import FXBook, FXRate
from portfolio_research_desk.paper_domain import Quote, Sector
from portfolio_research_desk.portfolio_risk import MarketSnapshot
from portfolio_research_desk.rebalancing import SignalBundle


def table(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise DataError(f"{label}: expected fields {', '.join(sorted(keys))}.")
    return value


def text_field(value, label):
    if not isinstance(value, str) or not value.strip():
        raise DataError(f"{label} must be a nonempty string.")
    return value


def stamp(value, label):
    try:
        result = datetime.fromisoformat(text_field(value, label))
        require_utc(result)
        return result
    except ValueError as exc:
        raise DataError(f"{label} must be an ISO timestamp with explicit UTC timezone.") from exc


def decimal_field(value, label):
    if type(value) not in (str, int, Decimal):
        raise DataError(f"{label} must be a decimal string or integer, never a float/boolean.")
    try:
        number = Decimal(value)
        if not number.is_finite():
            raise DataError(f"{label} must be finite.")
        return number
    except InvalidOperation as exc:
        raise DataError(f"{label} must be a valid decimal string.") from exc


def asset_id(value):
    parts = text_field(value, "asset").split(":")
    if len(parts) != 4:
        raise DataError("asset requires MARKET:EXCHANGE:SYMBOL:CURRENCY.")
    return AssetId(*parts)


def rows(value, label):
    if not isinstance(value, list):
        raise DataError(f"{label} must be an array.")
    return value


@dataclass(frozen=True)
class PaperInput:
    purpose: str
    as_of: datetime
    data_kind: str
    market: MarketSnapshot
    bundle: SignalBundle | None = None
    sessions: tuple[TradingSession, ...] = ()
    target: TargetPortfolio | None = None


def parse_paper_input(document, expected_purpose=None):
    common = {
        "schema_version",
        "purpose",
        "as_of",
        "data_kind",
        "source",
        "prices",
        "sectors",
        "fx",
    }
    if not isinstance(document, dict):
        raise DataError("Paper snapshot must be a JSON object.")
    purpose = document.get("purpose")
    if not isinstance(purpose, str) or purpose not in {"decision", "execution", "valuation"}:
        raise DataError("Paper snapshot purpose must be decision, execution or valuation.")
    if expected_purpose is not None and purpose != expected_purpose:
        raise DataError(f"Expected a {expected_purpose} snapshot, received {purpose}.")
    expected = common | ({"universe", "signals", "sessions"} if purpose == "decision" else set())
    if purpose == "decision" and "target" in document:
        expected.add("target")
    table(document, expected, "snapshot")
    if type(document["schema_version"]) is not int or document["schema_version"] != 6:
        raise DataError("Readable paper snapshot requires schema_version integer 6.")
    kind = document["data_kind"]
    if not isinstance(kind, str) or kind not in {"synthetic", "paper_observed"}:
        raise DataError(
            "data_kind must be synthetic or paper_observed; no historical PIT claim is supported."
        )
    synthetic = kind == "synthetic"
    at, source = stamp(document["as_of"], "as_of"), text_field(document["source"], "source")
    quotes, sectors, fx = [], [], []
    for row in rows(document["prices"], "prices"):
        table(
            row,
            {
                "asset",
                "observed_at",
                "available_at",
                "price",
                "kind",
                "tradable",
                "volume",
                "adjusted",
            },
            "price",
        )
        if not isinstance(row["kind"], str):
            raise DataError("price.kind must be a string.")
        quotes.append(
            Quote(
                asset_id(row["asset"]),
                stamp(row["observed_at"], "price.observed_at"),
                stamp(row["available_at"], "price.available_at"),
                decimal_field(row["price"], "price"),
                row["kind"],
                row["tradable"],
                row["volume"],
                row["adjusted"],
                source,
                synthetic,
            )
        )
    for row in rows(document["sectors"], "sectors"):
        table(row, {"asset", "name", "effective_at", "available_at"}, "sector")
        sectors.append(
            Sector(
                asset_id(row["asset"]),
                text_field(row["name"], "sector.name"),
                stamp(row["effective_at"], "sector.effective_at"),
                stamp(row["available_at"], "sector.available_at"),
            )
        )
    for row in rows(document["fx"], "fx"):
        table(row, {"observed_at", "available_at", "cad_per_usd"}, "fx")
        fx.append(
            FXRate(
                stamp(row["observed_at"], "fx.observed_at"),
                stamp(row["available_at"], "fx.available_at"),
                decimal_field(row["cad_per_usd"], "cad_per_usd"),
                source,
                synthetic,
            )
        )
    market = MarketSnapshot(tuple(quotes), FXBook(tuple(fx)), tuple(sectors))
    if not synthetic and any(q.asset.symbol.startswith("SYN_") for q in quotes):
        raise DataError("Synthetic asset identifiers cannot be relabelled paper_observed.")
    # Every supplied reference must already be known. Other service invariants are
    # rechecked by the planner/simulator/valuer with the account's actual limits.
    if any(q.available_at > at for q in market.quotes):
        raise DataError("A price is unavailable at snapshot as_of.")
    if purpose != "decision":
        return PaperInput(purpose, at, kind, market)
    u = table(
        document["universe"],
        {"universe_id", "as_of", "available_at", "membership_type", "assets"},
        "universe",
    )
    universe = UniverseSnapshot(
        text_field(u["universe_id"], "universe_id"),
        stamp(u["as_of"], "universe.as_of"),
        text_field(u["membership_type"], "membership_type"),
        tuple(asset_id(a) for a in rows(u["assets"], "universe.assets")),
        source,
        stamp(u["available_at"], "universe.available_at"),
        synthetic,
        ("Caller-supplied membership; no verified historical PIT certification.",),
    )
    if universe.membership_type == "point_in_time":
        raise DataError("Readable Paper inputs cannot manufacture verified PIT membership.")
    signals = []
    for row in rows(document["signals"], "signals"):
        table(
            row,
            {"asset", "score", "observation_start", "observation_end", "available_at"},
            "signal",
        )
        signals.append(
            Signal(
                asset_id(row["asset"]),
                at,
                stamp(row["observation_start"], "signal.observation_start"),
                stamp(row["observation_end"], "signal.observation_end"),
                stamp(row["available_at"], "signal.available_at"),
                decimal_field(row["score"], "signal.score"),
            )
        )
    sessions = []
    for row in rows(document["sessions"], "sessions"):
        table(row, {"date", "open_at", "close_at"}, "session")
        try:
            day = date.fromisoformat(text_field(row["date"], "session.date"))
        except ValueError as exc:
            raise DataError("session.date must be an ISO date.") from exc
        sessions.append(
            TradingSession(
                day,
                stamp(row["open_at"], "session.open_at"),
                stamp(row["close_at"], "session.close_at"),
            )
        )
    bundle = SignalBundle(tuple(signals), universe, source, kind)
    bundle.validate(at, "paper")
    target = None
    if "target" in document:
        value = table(document["target"], {"weights", "cash_weight"}, "target")
        weights = []
        for row in rows(value["weights"], "target.weights"):
            table(row, {"asset", "weight"}, "target.weight")
            weights.append((asset_id(row["asset"]), decimal_field(row["weight"], "target.weight")))
        target = TargetPortfolio(
            at, tuple(weights), decimal_field(value["cash_weight"], "cash_weight")
        )
    return PaperInput(purpose, at, kind, market, bundle, tuple(sessions), target)


def load_paper_input(path: Path, expected_purpose=None):
    try:
        document = json.loads(path.read_text("utf-8"), parse_float=Decimal)
        return parse_paper_input(document, expected_purpose)
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise DataError(f"Cannot read a valid Paper snapshot: {exc}") from exc
