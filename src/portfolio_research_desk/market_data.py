"""Typed synthetic fixture reader with an explicit, complete session schedule."""

import csv
import io
import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from importlib.resources import files

from portfolio_research_desk.domain import AssetId, PriceBar, TradingSession, fingerprint
from portfolio_research_desk.errors import DataError

FIELDS = [
    "market",
    "exchange",
    "symbol",
    "session_date",
    "open_at",
    "event_time",
    "observation_end",
    "available_at",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "currency",
    "adjusted",
    "source",
    "tradable",
]


@dataclass(frozen=True)
class MarketDataset:
    bars: tuple[PriceBar, ...]
    sessions: tuple[TradingSession, ...]
    synthetic: bool = True
    corporate_actions: str = "none"
    source: str = "synthetic_v1"

    @property
    def data_hash(self) -> str:
        return fingerprint(self)


def validate_dataset(dataset: MarketDataset) -> None:
    """Require complete panels; never infer missing sessions from observed rows."""
    if dataset.synthetic is not True or dataset.source != "synthetic_v1":
        raise DataError("Phase 1 accepts synthetic_v1 fixtures only.")
    if dataset.corporate_actions != "none":
        raise DataError("Corporate actions are not supported; cannot ignore splits/dividends.")
    dates = [s.session_date for s in dataset.sessions]
    if len(dates) < 3 or dates != sorted(set(dates)):
        raise DataError("At least three strictly ordered explicit sessions are required.")
    schedule = {s.session_date: s for s in dataset.sessions}
    for earlier, later in zip(dataset.sessions, dataset.sessions[1:], strict=False):
        if earlier.decision_at >= later.open_at:
            raise DataError("Sessions overlap the next execution time.")
    assets = {bar.asset for bar in dataset.bars}
    if not assets:
        raise DataError("Empty price panel.")
    seen = set()
    for bar in dataset.bars:
        if (
            bar.asset.market != "US"
            or bar.asset.exchange != "SYNTHETIC"
            or not bar.asset.symbol.startswith("SYN_")
            or bar.asset.currency != "USD"
            or bar.adjusted
            or bar.source != dataset.source
        ):
            raise DataError("Only raw USD synthetic prices are supported.")
        session = schedule.get(bar.session_date)
        if session is None or (bar.open_at, bar.event_time) != (session.open_at, session.close_at):
            raise DataError("Bar does not match the explicit session schedule.")
        key = (bar.asset, bar.session_date)
        if key in seen:
            raise DataError("Duplicate asset/session bar.")
        seen.add(key)
    if len(seen) != len(assets) * len(schedule):
        raise DataError("Incomplete price panel: missing session rows must not be filled.")


def parse_synthetic_dataset(csv_bytes: bytes, manifest_bytes: bytes) -> MarketDataset:
    try:
        meta = tomllib.loads(manifest_bytes.decode("utf-8"))
        required = {"synthetic", "source", "corporate_actions", "sessions"}
        if set(meta) != required:
            raise DataError("Invalid fixture manifest fields.")
        if not isinstance(meta["sessions"], list) or any(
            not isinstance(item, dict) or set(item) != {"date", "open_at", "close_at"}
            for item in meta["sessions"]
        ):
            raise DataError("Session manifest records require date, open_at and close_at only.")
        sessions = tuple(
            TradingSession(
                date.fromisoformat(item["date"]),
                datetime.fromisoformat(item["open_at"]),
                datetime.fromisoformat(item["close_at"]),
            )
            for item in meta["sessions"]
        )
        reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
        if reader.fieldnames != FIELDS:
            raise DataError("Invalid synthetic CSV columns.")
        bars = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise DataError("Malformed price row.")
            if row["adjusted"] not in {"true", "false"} or row["tradable"] not in {"true", "false"}:
                raise DataError("Invalid boolean in price row.")
            bars.append(
                PriceBar(
                    AssetId(row["market"], row["exchange"], row["symbol"], row["currency"]),
                    date.fromisoformat(row["session_date"]),
                    datetime.fromisoformat(row["open_at"]),
                    datetime.fromisoformat(row["event_time"]),
                    datetime.fromisoformat(row["observation_end"]),
                    datetime.fromisoformat(row["available_at"]),
                    Decimal(row["open"]) if row["open"] else None,
                    Decimal(row["high"]),
                    Decimal(row["low"]),
                    Decimal(row["close"]),
                    int(row["volume"]),
                    row["tradable"] == "true",
                    row["adjusted"] == "true",
                    row["source"],
                )
            )
        dataset = MarketDataset(
            tuple(sorted(bars, key=lambda b: (b.session_date, b.asset))),
            sessions,
            meta["synthetic"],
            meta["corporate_actions"],
            meta["source"],
        )
    except (ValueError, KeyError, TypeError, UnicodeError, csv.Error, InvalidOperation) as exc:
        raise DataError("Cannot parse the synthetic dataset and session manifest.") from exc
    validate_dataset(dataset)
    return dataset


def load_backtest_dataset() -> MarketDataset:
    try:
        root = files("portfolio_research_desk").joinpath("resources")
        return parse_synthetic_dataset(
            root.joinpath("backtest_prices.csv").read_bytes(),
            root.joinpath("backtest_sessions.toml").read_bytes(),
        )
    except OSError as exc:
        raise DataError("Cannot read the packaged backtest dataset.") from exc
