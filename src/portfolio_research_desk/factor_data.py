"""US French research factors: explicit percent conversion and retrieved vintages."""

import calendar
import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from portfolio_research_desk.data_adapters import DEFAULT_RETRY_POLICY, http_get, retry_call
from portfolio_research_desk.data_cache import SnapshotCache
from portfolio_research_desk.domain import fingerprint, jsonable, require_utc
from portfolio_research_desk.errors import DataError

BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FACTOR_NAMES = ("Mkt-RF", "SMB", "HML", "Mom")
MOM_DEFINITION = (
    "French US Mom: half (Small High + Big High) minus half (Small Low + Big Low), "
    "six value-weight portfolios sorted on size and prior (2-12) returns; "
    "daily and monthly constructions use their respective French definitions."
)


@dataclass(frozen=True)
class FactorRow:
    period: date
    mkt_rf: Decimal | None
    smb: Decimal | None
    hml: Decimal | None
    rf: Decimal | None
    mom: Decimal | None


@dataclass(frozen=True)
class FactorData:
    frequency: str
    rows: tuple[FactorRow, ...]
    source: str
    retrieved_at: datetime
    source_hashes: dict[str, str]
    synthetic: bool
    input_unit: str = "percent"
    unit: str = "decimal_return"
    market: str = "US"
    currency: str = "USD"
    availability_basis: str = "retrieved_snapshot"
    momentum_definition: str = MOM_DEFINITION

    def __post_init__(self):
        require_utc(self.retrieved_at)
        if self.frequency not in {"daily", "monthly"} or not self.rows:
            raise DataError("Factors require daily/monthly frequency and nonempty rows.")
        if (
            self.input_unit != "percent"
            or self.unit != "decimal_return"
            or self.market != "US"
            or self.currency != "USD"
            or self.availability_basis != "retrieved_snapshot"
        ):
            raise DataError("Unsupported factor unit/market/currency/availability contract.")
        periods = [r.period for r in self.rows]
        if periods != sorted(set(periods)):
            raise DataError("Factor dates must be unique and ordered.")
        for row in self.rows:
            if type(row.period) is not date or (
                self.frequency == "monthly"
                and row.period.day != calendar.monthrange(row.period.year, row.period.month)[1]
            ):
                raise DataError("Monthly factors require canonical calendar month-end labels.")
            for value in (row.mkt_rf, row.smb, row.hml, row.rf, row.mom):
                if value is not None and (not isinstance(value, Decimal) or not value.is_finite()):
                    raise DataError("Factor values must be finite decimal returns or missing.")
            if row.period > self.retrieved_at.date():
                raise DataError("Factor period occurs after snapshot retrieval.")

    @property
    def snapshot_hash(self):
        return fingerprint(self)


def _period(value: str, frequency: str) -> date:
    try:
        if frequency == "daily" and re.fullmatch(r"\d{8}", value):
            return datetime.strptime(value, "%Y%m%d").date()
        if frequency == "monthly" and re.fullmatch(r"\d{6}", value):
            parsed = datetime.strptime(value, "%Y%m")
            return date(
                parsed.year, parsed.month, calendar.monthrange(parsed.year, parsed.month)[1]
            )
    except ValueError as exc:
        raise DataError("Invalid French factor date.") from exc
    raise DataError("Factor date/frequency mismatch; no implicit resampling.")


def parse_french_table(raw: bytes, frequency: str, momentum: bool = False) -> dict:
    """Read only the first daily/monthly return table; never consume annual summaries."""
    if frequency not in {"daily", "monthly"}:
        raise DataError("Unsupported factor frequency.")
    if len(raw) > 32_000_000:
        raise DataError("Factor input exceeds the 32 MB limit.")
    if raw.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = [m for m in archive.infolist() if m.filename.lower().endswith(".csv")]
                if len(members) != 1 or members[0].file_size > 32_000_000:
                    raise DataError("Expected one bounded CSV in the French ZIP.")
                raw = archive.read(members[0])
        except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
            raise DataError("Invalid French ZIP archive.") from exc
    try:
        records = csv.reader(io.StringIO(raw.decode("utf-8-sig")))
        expected = ["Mom"] if momentum else ["Mkt-RF", "SMB", "HML", "RF"]
        found, rows = False, {}
        for record in records:
            cells = [v.strip() for v in record]
            if not found:
                if cells and cells[1:] == expected:
                    found = True
                continue
            if not cells or not cells[0]:
                if rows:
                    break
                continue
            if not cells[0].isdigit():
                raise DataError("Unexpected non-date row inside the factor table.")
            period = _period(cells[0], frequency)
            if period in rows or len(cells) != len(expected) + 1:
                raise DataError("Duplicate date or malformed factor row.")
            values = []
            for text in cells[1:]:
                value = Decimal(text) if text else None
                if value is not None and not value.is_finite():
                    raise DataError("Nonfinite factor value.")
                # French missing codes must be identified BEFORE scaling.
                if value in {None, Decimal("-99.99"), Decimal("-999")}:
                    values.append(None)
                else:
                    # Construct the exponent shift exactly: arithmetic/scaleb would
                    # inherit the caller's precision, rounding and exponent limits.
                    sign, digits, exponent = value.as_tuple()
                    values.append(Decimal((sign, digits, exponent - 2)))
            rows[period] = tuple(values)
        if not found or not rows:
            raise DataError("French factor header/table is missing or incompatible.")
        return dict(sorted(rows.items()))
    except (UnicodeError, csv.Error, InvalidOperation) as exc:
        raise DataError("Cannot parse French percent-return CSV.") from exc


def combine_factors(
    ff3: bytes,
    momentum: bytes,
    frequency: str,
    retrieved_at: datetime,
    source: str,
    synthetic: bool = False,
) -> FactorData:
    three = parse_french_table(ff3, frequency)
    mom = parse_french_table(momentum, frequency, True)
    return FactorData(
        frequency,
        tuple(
            FactorRow(period, *values, mom.get(period, (None,))[0])
            for period, values in three.items()
        ),
        source,
        retrieved_at,
        {"ff3": hashlib.sha256(ff3).hexdigest(), "mom": hashlib.sha256(momentum).hexdigest()},
        synthetic,
    )


def factors_from_dict(value: dict) -> FactorData:
    try:
        fields = dict(value)
        fields["retrieved_at"] = datetime.fromisoformat(fields["retrieved_at"])
        fields["rows"] = tuple(
            FactorRow(
                date.fromisoformat(r["period"]),
                *(
                    Decimal(r[k]) if r[k] is not None else None
                    for k in ("mkt_rf", "smb", "hml", "rf", "mom")
                ),
            )
            for r in fields["rows"]
        )
        return FactorData(**fields)
    except (ValueError, TypeError, KeyError, InvalidOperation) as exc:
        raise DataError("Invalid factor snapshot schema.") from exc


class FrenchAdapter:
    """Known US endpoints, immutable cache, bounded retries; no invented release times."""

    def __init__(self, cache_dir: Path, transport=http_get, clock=lambda: datetime.now(UTC)):
        self.cache = SnapshotCache(cache_dir)
        self.transport, self.clock = transport, clock

    def fetch(self, frequency="daily", offline=False, refresh=False, allow_stale=False):
        if frequency not in {"daily", "monthly"}:
            raise DataError("French supports daily/monthly only.")
        suffix = "_daily" if frequency == "daily" else ""
        urls = [
            BASE_URL + name + suffix + "_CSV.zip"
            for name in ("F-F_Research_Data_Factors", "F-F_Momentum_Factor")
        ]
        # v1 normalization depended on the caller's Decimal context. Those cached
        # normalized values cannot be repaired from hashes alone; fetch afresh.
        key = fingerprint({"adapter": "french_us_v2", "urls": urls})
        entry = (
            None
            if refresh
            else self.cache.get(key, "real", self.clock(), timedelta(hours=24), allow_stale)
        )
        if entry:
            result = factors_from_dict(entry.value)
            if result.frequency != frequency or result.synthetic:
                raise DataError("Factor cache identity mismatch.")
            return result, {"hit": True, "stale": entry.stale, "urls": urls}
        if offline:
            raise DataError("Offline French cache miss/expiry; no request was made.")
        raw = [
            retry_call(lambda url=url: self.transport(url, 15), DEFAULT_RETRY_POLICY)
            for url in urls
        ]
        result = combine_factors(*raw, frequency, self.clock(), " | ".join(urls))
        self.cache.put(key, "real", jsonable(result), self.clock(), repair=refresh)
        return result, {"hit": False, "stale": False, "urls": urls}


def require_factor_signal_use(data: FactorData, decision_at: datetime) -> None:
    """Phase 3 vintages never certify historical public availability for signals."""
    require_utc(decision_at)
    if data.retrieved_at > decision_at:
        raise DataError("Factor snapshot was unavailable at the historical decision.")
    raise DataError("Factor release vintages are unverified; descriptive attribution only.")
