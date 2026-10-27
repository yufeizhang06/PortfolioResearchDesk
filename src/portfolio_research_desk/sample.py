"""Read the tiny, fixed synthetic fixture; this is not a market-data adapter."""

import csv
import hashlib
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from importlib.resources import files

from portfolio_research_desk.errors import SampleError

_FIELDS = [
    "market",
    "exchange",
    "symbol",
    "session_date",
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
]


def summarize_sample() -> dict[str, object]:
    """Check the packaged fixture and return descriptive metadata only.

    Timestamps are synthetic UTC assumptions. No decision, label, signal, order
    or performance metric is constructed here.
    """
    try:
        raw = (
            files("portfolio_research_desk").joinpath("resources/synthetic_prices.csv").read_bytes()
        )
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
        if reader.fieldnames != _FIELDS:
            raise SampleError("Synthetic sample has unexpected columns.")
        rows = list(reader)
        if not rows:
            raise SampleError("Synthetic sample is empty.")
        seen = set()
        for row in rows:
            if None in row or any(value is None for value in row.values()):
                raise SampleError("Synthetic sample has an incomplete row.")
            session = date.fromisoformat(row["session_date"])
            key = (row["market"], row["exchange"], row["symbol"], session)
            if key in seen:
                raise SampleError("Synthetic sample has duplicate asset/session rows.")
            seen.add(key)
            if (
                row["market"] != "US"
                or row["exchange"] != "SYNTHETIC"
                or not row["symbol"].startswith("SYN_")
                or row["currency"] != "USD"
                or row["adjusted"] != "false"
                or row["source"] != "synthetic_v1"
            ):
                raise SampleError("Synthetic sample identity/source/currency is invalid.")
            prices = [Decimal(row[name]) for name in ("open", "high", "low", "close")]
            if any(not price.is_finite() or price <= 0 for price in prices):
                raise SampleError("Synthetic OHLC prices must be finite and positive.")
            opening, high, low, close = prices
            if not (low <= min(opening, close) <= max(opening, close) <= high):
                raise SampleError("Synthetic OHLC bounds are invalid.")
            if int(row["volume"]) <= 0:
                raise SampleError("Synthetic volume must be positive.")
            times = [
                datetime.fromisoformat(row[name])
                for name in ("event_time", "observation_end", "available_at")
            ]
            if any(t.tzinfo is None or t.utcoffset().total_seconds() != 0 for t in times):
                raise SampleError("Synthetic timestamps must be timezone-aware UTC.")
            event, observed, available = times
            if not (event == observed <= available and event.date() == session):
                raise SampleError("Synthetic event/observation/availability times are invalid.")
    except (OSError, UnicodeError, csv.Error, ValueError, InvalidOperation) as exc:
        raise SampleError("Cannot read valid packaged synthetic prices.") from exc

    sessions = sorted({row["session_date"] for row in rows})
    return {
        "synthetic": True,
        "source": "synthetic_v1",
        "currency": "USD",
        "adjusted": False,
        "rows": len(rows),
        "symbols": sorted({row["symbol"] for row in rows}),
        "session_start": sessions[0],
        "session_end": sessions[-1],
        "sha256": hashlib.sha256(raw).hexdigest(),
        "limitations": [
            "Fictional assets and prices; not a real exchange calendar or historical PIT dataset.",
            "UTC availability is a fixture assumption, not verified vendor publication timing.",
            "Phase 0 metadata only; no signals, backtest, accounts, FX or investment performance.",
        ],
    }
