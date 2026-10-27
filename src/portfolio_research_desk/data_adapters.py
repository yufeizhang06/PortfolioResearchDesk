"""Provider and local-file adapters share the same provenance-bearing History contract."""

import csv
import hashlib
import io
import json
import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from datetime import time as daytime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from functools import wraps
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from portfolio_research_desk.data_contracts import History, Observation, history_from_dict
from portfolio_research_desk.domain import AssetId, jsonable
from portfolio_research_desk.errors import DataError

_LOG = logging.getLogger(__name__)
CSV_FIELDS = [
    "market",
    "exchange",
    "symbol",
    "currency",
    "session_date",
    "event_time",
    "observation_end",
    "available_at",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "adj_close",
    "dividend",
    "split_ratio",
]


class ProviderError(DataError):
    def __init__(self, code: str, message: str, retryable: bool = False, retry_after: float = 0):
        super().__init__(f"{code}: {message}")
        self.code, self.retryable, self.retry_after = code, retryable, retry_after


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 3
    timeout: float = 15
    base_delay: float = 0.5
    max_delay: float = 5

    def __post_init__(self) -> None:
        if not 1 <= self.attempts <= 5 or not 0 < self.timeout <= 60:
            raise DataError("Retry attempts must be 1-5 and timeout in (0,60].")
        if self.base_delay < 0 or self.max_delay < self.base_delay or self.max_delay > 10:
            raise DataError("Invalid bounded retry delays.")


DEFAULT_RETRY_POLICY = RetryPolicy()


def retry_call[T](
    call: Callable[[], T], policy: RetryPolicy, sleep: Callable[[float], None] = time.sleep
) -> T:
    for attempt in range(policy.attempts):
        try:
            return call()
        except ProviderError as exc:
            if (
                not exc.retryable
                or attempt + 1 == policy.attempts
                or exc.retry_after > policy.max_delay
            ):
                raise
            delay = max(exc.retry_after, min(policy.max_delay, policy.base_delay * 2**attempt))
            _LOG.warning("Provider retry %s (%d/%d)", exc.code, attempt + 1, policy.attempts)
            sleep(delay)
    raise AssertionError("Unreachable retry state")


def _retry_after_seconds(value: str, now: datetime) -> float:
    try:
        delay = float(value)
    except ValueError:
        try:
            delay = (parsedate_to_datetime(value) - now).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return 0
    return max(0, delay) if math.isfinite(delay) else 0


def http_get(url: str, timeout: float) -> bytes:
    try:
        request = Request(url, headers={"User-Agent": "PortfolioResearchDesk/0.3 research client"})
        with urlopen(request, timeout=timeout) as response:
            content = response.read(20 * 1024 * 1024 + 1)
        if len(content) > 20 * 1024 * 1024:
            raise ProviderError("OVERSIZED_RESPONSE", "Provider response exceeds 20 MiB.")
        return content
    except HTTPError as exc:
        wait = _retry_after_seconds(exc.headers.get("Retry-After", "0"), datetime.now(UTC))
        raise ProviderError(
            f"HTTP_{exc.code}", "Remote request failed.", exc.code == 429 or exc.code >= 500, wait
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ProviderError("CONNECTION", "Remote connection failed or timed out.", True) from exc


class HistoryAdapter(Protocol):
    def cache_identity(self) -> dict[str, Any]: ...
    def fetch(self, asset: AssetId, start: date, end: date) -> History: ...


def _number(value: Any) -> Decimal | None:
    if value is None or str(value).strip() in {"", "None", "<NA>"}:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal("NaN")


def _volume(value: Any) -> int | None:
    parsed = _number(value)
    if parsed is None or not parsed.is_finite() or parsed != parsed.to_integral_value():
        return None
    return int(parsed)


class YFinanceAdapter:
    """Yahoo via third-party yfinance; retrieved history is explicitly NOT historical PIT."""

    def __init__(
        self,
        cache_dir: Path,
        policy: RetryPolicy = DEFAULT_RETRY_POLICY,
        factory: Callable[[str], Any] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.policy, self.clock, self.sleep = policy, clock, sleep
        if factory is None:
            try:
                import yfinance as yf
            except ImportError as exc:
                raise DataError("Install the data extra: uv sync --locked --extra data.") from exc
            yf.set_tz_cache_location(str(cache_dir / "yfinance_internal"))
            self.factory, self.version = yf.Ticker, yf.__version__
        else:
            self.factory, self.version = factory, "injected_test_transport"

    def cache_identity(self) -> dict[str, Any]:
        return {
            "adapter": "yfinance",
            "version": self.version,
            "schema": 1,
            "auto_adjust": False,
            "back_adjust": False,
            "repair": False,
            "interval": "1d",
        }

    def fetch(self, asset: AssetId, start: date, end: date) -> History:
        if (
            start >= end
            or asset.market != "US"
            or asset.currency != "USD"
            or asset.symbol.startswith("SYN_")
        ):
            raise DataError("Yahoo requests require real US/USD assets and start < exclusive end.")

        def request() -> History:
            try:
                ticker = self.factory(asset.symbol.replace(".", "-"))
                frame = ticker.history(
                    start=start.isoformat(),
                    end=end.isoformat(),
                    interval="1d",
                    auto_adjust=False,
                    back_adjust=False,
                    repair=False,
                    actions=True,
                    keepna=True,
                    rounding=False,
                    raise_errors=True,
                    timeout=self.policy.timeout,
                )
                metadata = ticker.get_history_metadata()
            except Exception as exc:
                label = type(exc).__name__.lower()
                code = (
                    "RATE_LIMIT"
                    if "ratelimit" in label or "429" in str(exc)
                    else "PROVIDER_FAILURE"
                )
                missing = any(
                    word in label for word in ("pricesmissing", "tckrmissing", "invalidperiod")
                )
                raise ProviderError(
                    "NO_DATA" if missing else code,
                    f"Yahoo request failed for {asset.symbol}; no fallback data.",
                    not missing,
                ) from exc
            if frame is None or frame.empty:
                raise ProviderError("EMPTY", f"No rows for {asset.symbol}; coverage is unknown.")
            if not isinstance(metadata, dict):
                raise ProviderError("SCHEMA", "Provider identity metadata is unavailable.")
            exchange_map = {
                "NMS": "XNAS",
                "NGM": "XNAS",
                "NCM": "XNAS",
                "NYQ": "XNYS",
                "ASE": "XASE",
                "PCX": "ARCX",
                "BTS": "BATS",
            }
            exchange = exchange_map.get(metadata.get("exchangeName"))
            if metadata.get("currency") != asset.currency or exchange != asset.exchange:
                raise ProviderError(
                    "IDENTITY", f"Provider currency/exchange does not verify {asset.symbol}."
                )
            try:
                timezone = ZoneInfo(metadata["exchangeTimezoneName"])
            except (KeyError, ZoneInfoNotFoundError) as exc:
                raise ProviderError(
                    "TIMEZONE", "Provider exchange timezone is unavailable."
                ) from exc
            retrieved = self.clock()
            rows = []
            required = {"Open", "High", "Low", "Close", "Volume"}
            if not required <= set(frame.columns):
                raise ProviderError("SCHEMA", "Provider daily OHLCV schema changed.")
            for stamp, item in frame.iterrows():
                if stamp.tzinfo is None:
                    raise ProviderError("TIMEZONE", "Provider index is timezone-naive.")
                session_date = stamp.tz_convert(timezone).date()
                if not start <= session_date < end:
                    raise ProviderError(
                        "DATE_RANGE", "Provider returned a row outside the request."
                    )
                # A conservative local-date upper bound, NEVER invented as the actual closing event.
                bound = datetime.combine(
                    session_date + timedelta(days=1), daytime(), timezone
                ).astimezone(UTC)
                rows.append(
                    Observation(
                        asset,
                        session_date,
                        None,
                        bound,
                        retrieved,
                        *(_number(item[name]) for name in ("Open", "High", "Low", "Close")),
                        _volume(item["Volume"]),
                        _number(item.get("Adj Close")),
                        _number(item.get("Dividends", 0)),
                        _number(item.get("Stock Splits", 0)),
                    )
                )
            return History(
                "real",
                f"Yahoo via yfinance {self.version}",
                "provider_ohlc",
                "retrieved_snapshot",
                retrieved,
                tuple(rows),
                (
                    "Yahoo via yfinance is third-party research data, not an official API.",
                    "Daily event_time is unknown; observation_end is a local-date upper bound.",
                    "Disabled adjustment/repair does not prove historical tradable prices or PIT.",
                    "Historical index membership and delisted-security coverage are not verified.",
                ),
                "exchange_local_date_upper_bound",
            )

        return retry_call(request, self.policy, self.sleep)


def _native_rows(history: History) -> list[dict[str, Any]]:
    output = []
    for row in history.rows:
        item = jsonable(row)
        item.update(item.pop("asset"))
        output.append(item)
    return output


def _local_io_boundary(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except OSError as exc:
            raise DataError("Local history I/O failed; export may be incomplete.") from exc

    return wrapped


@_local_io_boundary
def write_history(history: History, path: Path) -> None:
    """Export a native CSV+metadata pair or a Parquet file with embedded metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise DataError("History export already exists; refusing to overwrite.")
    metadata = jsonable(history)
    del metadata["rows"]
    if path.suffix.lower() == ".csv":
        sidecar = path.with_suffix(".metadata.json")
        if sidecar.exists():
            raise DataError("CSV provenance sidecar already exists.")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(_native_rows(history))
        content = stream.getvalue().encode("utf-8")
        metadata["content_sha256"] = hashlib.sha256(content).hexdigest()
        with path.open("xb") as output:
            output.write(content)
        with sidecar.open("x", encoding="utf-8") as output:
            json.dump({"schema_version": 1, "history": metadata}, output, indent=2)
    elif path.suffix.lower() == ".parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise DataError("Install the data extra for Parquet support.") from exc
        rows = _native_rows(history)
        # Exact decimal and UTC text avoid float coercion and platform-dependent timestamps.
        table = pa.table(
            {
                name: [str(row[name]) if row[name] is not None else None for row in rows]
                for name in CSV_FIELDS
            }
        )
        table = table.replace_schema_metadata(
            {
                b"portfolio_research_desk": json.dumps(
                    {"schema_version": 1, "history": metadata}
                ).encode("utf-8")
            }
        )
        with path.open("xb") as output:
            pq.write_table(table, output)
    else:
        raise DataError("History export supports .csv or .parquet only.")


class LocalHistoryAdapter:
    """CSV and Parquet must contain explicit, versioned provenance; no inference."""

    def __init__(self, path: Path):
        self.path = path

    def cache_identity(self) -> dict[str, Any]:
        try:
            content = self.path.read_bytes()
            if self.path.suffix.lower() == ".csv":
                content += self.path.with_suffix(".metadata.json").read_bytes()
            return {
                "adapter": self.path.suffix.lower(),
                "content_hash": hashlib.sha256(content).hexdigest(),
                "schema": 1,
            }
        except OSError as exc:
            raise DataError("Local history or required provenance sidecar cannot be read.") from exc

    def read(self) -> History:
        try:
            if self.path.suffix.lower() == ".csv":
                content = self.path.read_bytes()
                meta = json.loads(self.path.with_suffix(".metadata.json").read_text("utf-8"))
                expected = meta["history"].pop("content_sha256")
                if hashlib.sha256(content).hexdigest() != expected:
                    raise DataError("CSV provenance checksum mismatch.")
                reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
                if reader.fieldnames != CSV_FIELDS:
                    raise DataError("Native CSV column contract does not match.")
                records = list(reader)
            elif self.path.suffix.lower() == ".parquet":
                try:
                    import pyarrow.parquet as pq
                except ImportError as exc:
                    raise DataError("Install the data extra for Parquet support.") from exc
                table = pq.read_table(self.path)
                meta = json.loads(table.schema.metadata[b"portfolio_research_desk"])
                if table.column_names != CSV_FIELDS:
                    raise DataError("Native Parquet column contract does not match.")
                records = table.to_pylist()
            else:
                raise DataError("Local adapter supports CSV or Parquet only.")
            if meta["schema_version"] != 1:
                raise DataError("Unsupported native history schema version.")
            rows = []
            for record in records:
                if None in record or any(
                    record[k] is None
                    for k in (
                        "market",
                        "exchange",
                        "symbol",
                        "currency",
                        "session_date",
                        "observation_end",
                        "available_at",
                    )
                ):
                    raise DataError("Malformed native observation row.")
                item = {
                    k: record[k]
                    for k in CSV_FIELDS
                    if k not in {"market", "exchange", "symbol", "currency"}
                }
                item["asset"] = {k: record[k] for k in ("market", "exchange", "symbol", "currency")}
                item["event_time"] = item["event_time"] or None
                for field in (
                    "open",
                    "high",
                    "low",
                    "close",
                    "adj_close",
                    "dividend",
                    "split_ratio",
                ):
                    item[field] = (
                        str(parsed) if (parsed := _number(item[field])) is not None else None
                    )
                item["volume"] = _volume(item["volume"])
                rows.append(item)
            return history_from_dict({**meta["history"], "rows": rows})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise DataError("Cannot load local history with valid native provenance.") from exc

    def fetch(self, asset: AssetId, start: date, end: date) -> History:
        history = self.read()
        rows = tuple(r for r in history.rows if r.asset == asset and start <= r.session_date < end)
        if not rows:
            raise ProviderError(
                "LOCAL_EMPTY", f"No local rows for {asset.symbol} in the requested range."
            )
        return replace(history, rows=rows)
