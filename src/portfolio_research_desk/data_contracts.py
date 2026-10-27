"""Research observations with explicit provenance; distinct from executable Phase 1 bars."""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from portfolio_research_desk.domain import AssetId, fingerprint, require_utc
from portfolio_research_desk.errors import DataError


@dataclass(frozen=True)
class Observation:
    asset: AssetId
    session_date: date
    event_time: datetime | None
    observation_end: datetime
    available_at: datetime
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: int | None
    adj_close: Decimal | None = None
    dividend: Decimal = Decimal("0")
    split_ratio: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if type(self.session_date) is not date:
            raise DataError("session_date must be an explicit date.")
        for stamp in (self.observation_end, self.available_at):
            if not isinstance(stamp, datetime):
                raise DataError("Observation and availability timestamps are required.")
            require_utc(stamp)
        if self.event_time is not None:
            require_utc(self.event_time)


@dataclass(frozen=True)
class History:
    data_kind: str
    provider: str
    price_basis: str
    availability_basis: str
    retrieved_at: datetime
    rows: tuple[Observation, ...]
    limitations: tuple[str, ...] = ()
    timestamp_basis: str = "explicit_source_timestamps"

    def __post_init__(self) -> None:
        require_utc(self.retrieved_at)
        if self.data_kind not in {"real", "synthetic"} or not self.provider:
            raise DataError("History requires an explicit real/synthetic kind and provider.")
        if self.price_basis not in {
            "synthetic_raw",
            "raw_declared",
            "provider_ohlc",
            "provider_adjusted",
        }:
            raise DataError("Unknown price adjustment basis.")
        if self.availability_basis not in {"declared", "retrieved_snapshot"}:
            raise DataError("Unknown availability basis.")
        if not isinstance(self.rows, tuple) or not self.rows:
            raise DataError("A history snapshot must contain rows.")
        for row in self.rows:
            if (self.data_kind == "synthetic") != row.asset.symbol.startswith("SYN_"):
                raise DataError("Real and synthetic asset identities cannot be mixed.")
            if (
                self.availability_basis == "retrieved_snapshot"
                and row.available_at != self.retrieved_at
            ):
                raise DataError("Retrieved snapshots must preserve actual retrieval availability.")
        if self.data_kind == "real" and self.price_basis == "synthetic_raw":
            raise DataError("Real prices cannot use a synthetic basis.")

    @property
    def snapshot_hash(self) -> str:
        return fingerprint(self)


@dataclass(frozen=True)
class QualityIssue:
    asset: AssetId | None
    session_date: date | None
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class QualityReport:
    accepted: tuple[Observation, ...]
    quarantined: tuple[Observation, ...]
    issues: tuple[QualityIssue, ...]
    expected_calendar_verified: bool


def _session_time_issue(history: History, row: Observation) -> QualityIssue | None:
    """Check daily labels, never equate event time with download/publication time.

    Only the existing explicit-event and local-midnight-bound source contracts
    are understood. Exchange-local dates include extended hours, not a certified
    exchange trading calendar or proof of a historically published vintage.
    """
    explicit = history.timestamp_basis == "explicit_source_timestamps"
    upper_bound = history.timestamp_basis == "exchange_local_date_upper_bound"

    def mismatch(message):
        return QualityIssue(row.asset, row.session_date, "SESSION_TIME_MISMATCH", "ERROR", message)

    def unverified(message):
        return QualityIssue(
            row.asset,
            row.session_date,
            "SESSION_TIME_UNVERIFIED",
            "WARNING",
            message + " Descriptive only; ineligible for strict historical use.",
        )

    # A gap of more than one UTC date cannot represent this local daily session.
    # Preserve that rejection even if timezone data/source semantics are unavailable.
    stamps = [row.event_time] if row.event_time is not None else []
    if explicit or upper_bound:
        stamps.append(row.observation_end)
    if any(abs((stamp.date() - row.session_date).days) > 1 for stamp in stamps):
        return mismatch("Known daily timestamp contradicts the session date.")
    if row.asset.market != "US" or row.asset.exchange not in {
        "XNAS",
        "XNYS",
        "XASE",
        "ARCX",
        "BATS",
    }:
        return unverified("Exchange-local daily date semantics are unsupported.")
    try:
        zone = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        return unverified("IANA timezone data unavailable; session alignment not verified.")
    start = datetime.combine(row.session_date, time(), zone).astimezone(UTC)
    end = datetime.combine(row.session_date + timedelta(days=1), time(), zone).astimezone(UTC)
    if row.event_time is not None and not start <= row.event_time < end:
        return mismatch("Known event is outside its exchange-local session date.")
    if upper_bound:
        if row.observation_end != end:
            return mismatch("Daily observation bound is not the declared next local midnight.")
    elif explicit:
        if not start <= row.observation_end <= end:
            return mismatch("Explicit daily observation end contradicts the session date.")
    else:
        return unverified("Source timestamp_basis is not a supported daily contract.")
    if row.event_time is None:
        return unverified("Daily date bound checked; exact event time remains unknown.")
    return None


def validate_quality(
    history: History, expected_sessions: tuple[date, ...] | None = None
) -> QualityReport:
    counts = Counter((r.asset, r.session_date) for r in history.rows)
    issues, accepted, quarantined = [], [], []
    previous: dict[AssetId, Decimal] = {}
    for row in sorted(history.rows, key=lambda r: (r.asset, r.session_date)):
        problems = []
        prices = (row.open, row.high, row.low, row.close)
        if counts[row.asset, row.session_date] != 1:
            problems.append(("DUPLICATE", "Duplicate asset/session rows; all copies quarantined."))
        if any(p is None for p in prices):
            problems.append(("MISSING_PRICE", "Missing OHLC; no filling is performed."))
        elif any(not p.is_finite() or p <= 0 for p in prices):
            problems.append(("INVALID_PRICE", "OHLC must be finite and positive."))
        elif not (row.low <= min(row.open, row.close) <= max(row.open, row.close) <= row.high):
            problems.append(("OHLC_BOUNDS", "OHLC bounds are inconsistent."))
        if row.volume is None or type(row.volume) is not int or row.volume < 0:
            problems.append(("INVALID_VOLUME", "Volume must be an observed nonnegative integer."))
        if row.asset.currency != "USD":
            problems.append(("CURRENCY", "Phase 2 US research requires explicit USD prices."))
        if row.observation_end > row.available_at or (
            row.event_time and row.event_time > row.observation_end
        ):
            problems.append(("TIME_ORDER", "Observation period not complete at available_at."))
        time_issue = _session_time_issue(history, row)
        if time_issue:
            if time_issue.severity == "ERROR":
                problems.append((time_issue.code, time_issue.message))
            else:
                issues.append(time_issue)
        if row.adj_close is not None and (not row.adj_close.is_finite() or row.adj_close <= 0):
            problems.append(("ADJUSTED_PRICE", "Invalid supplied adjusted close."))
        if any(
            not isinstance(value, Decimal) or not value.is_finite() or value < 0
            for value in (row.dividend, row.split_ratio)
        ):
            problems.append(("CORPORATE_ACTION", "Invalid corporate action values."))
        if not problems and row.asset in previous and abs(row.close / previous[row.asset] - 1) > 1:
            problems.append(
                (
                    "EXTREME_JUMP",
                    "Price change over 100%; requires explicit review, never repaired.",
                )
            )
        if problems:
            quarantined.append(row)
            issues.extend(
                QualityIssue(row.asset, row.session_date, code, "ERROR", message)
                for code, message in problems
            )
        else:
            accepted.append(row)
            previous[row.asset] = row.close
            if row.volume == 0:
                issues.append(
                    QualityIssue(
                        row.asset,
                        row.session_date,
                        "ZERO_VOLUME",
                        "WARNING",
                        "No observed volume; not a tradability guarantee.",
                    )
                )
            if row.split_ratio not in {0, 1} or row.dividend != 0:
                issues.append(
                    QualityIssue(
                        row.asset,
                        row.session_date,
                        "CORPORATE_ACTION",
                        "WARNING",
                        "Action present; screening must review its lookback window.",
                    )
                )
    if expected_sessions is None:
        issues.append(
            QualityIssue(
                None,
                None,
                "CALENDAR_UNVERIFIED",
                "WARNING",
                "No authoritative exchange calendar supplied; gaps are not inferred as holidays.",
            )
        )
    else:
        for asset in {r.asset for r in history.rows}:
            observed = {r.session_date for r in history.rows if r.asset == asset}
            for missing in sorted(set(expected_sessions) - observed):
                issues.append(
                    QualityIssue(
                        asset,
                        missing,
                        "MISSING_SESSION",
                        "ERROR",
                        "Expected session absent; no forward/backward fill.",
                    )
                )
    if history.availability_basis == "retrieved_snapshot":
        issues.append(
            QualityIssue(
                None,
                None,
                "NOT_HISTORICAL_PIT",
                "WARNING",
                "Availability is retrieval time, not verified historical publication time.",
            )
        )
    if any(row.event_time is None for row in history.rows):
        issues.append(
            QualityIssue(
                None,
                None,
                "UNKNOWN_EVENT_TIME",
                "WARNING",
                "Exact event time unknown; the declared bound is descriptive research only.",
            )
        )
    return QualityReport(
        tuple(accepted), tuple(quarantined), tuple(issues), expected_sessions is not None
    )


def history_from_dict(value: dict[str, Any]) -> History:
    """Parse the versioned native representation; no inferred source metadata."""
    try:
        rows = []
        for item in value["rows"]:
            item = dict(item)
            item["asset"] = AssetId(**item["asset"])
            item["session_date"] = date.fromisoformat(item["session_date"])
            for key in ("event_time", "observation_end", "available_at"):
                item[key] = datetime.fromisoformat(item[key]) if item[key] is not None else None
            for key in ("open", "high", "low", "close", "adj_close", "dividend", "split_ratio"):
                item[key] = Decimal(item[key]) if item.get(key) is not None else None
            rows.append(Observation(**item))
        fields = {k: v for k, v in value.items() if k != "rows"}
        fields["retrieved_at"] = datetime.fromisoformat(fields["retrieved_at"])
        fields["limitations"] = tuple(fields["limitations"])
        return History(rows=tuple(rows), **fields)
    except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
        raise DataError("Invalid normalized history snapshot.") from exc
