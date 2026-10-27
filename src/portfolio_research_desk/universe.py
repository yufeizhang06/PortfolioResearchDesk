"""Custom watchlists, official current Nasdaq directory and historical-use guards."""

import csv
import hashlib
import io
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any

from portfolio_research_desk.data_adapters import (
    DEFAULT_RETRY_POLICY,
    RetryPolicy,
    http_get,
    retry_call,
)
from portfolio_research_desk.domain import (
    AssetId,
    UniverseSnapshot,
    fingerprint,
    jsonable,
    require_utc,
)
from portfolio_research_desk.errors import DataError

NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"


def custom_universe(
    assets: tuple[AssetId, ...], as_of: datetime, synthetic: bool
) -> UniverseSnapshot:
    unique = tuple(dict.fromkeys(assets))
    if not unique or any(a.market != "US" or a.currency != "USD" for a in unique):
        raise DataError("Custom universe requires nonempty explicit US/USD asset identities.")
    if any(a.symbol.startswith("SYN_") != synthetic for a in unique):
        raise DataError("Watchlist identities do not match the declared real/synthetic kind.")
    return UniverseSnapshot(
        f"custom-{fingerprint(unique)[:16]}",
        as_of,
        "user_static",
        unique,
        "user_watchlist",
        as_of,
        synthetic,
        ("User-selected static sample; no historical index membership or delisting coverage.",),
    )


def snapshot_from_dict(value: dict[str, Any]) -> UniverseSnapshot:
    try:
        values = dict(value)
        values["assets"] = tuple(AssetId(**a) for a in values["assets"])
        values["as_of"] = datetime.fromisoformat(values["as_of"])
        values["available_at"] = (
            datetime.fromisoformat(values["available_at"]) if values.get("available_at") else None
        )
        values["limitations"] = tuple(values.get("limitations", ()))
        return UniverseSnapshot(**values)
    except (ValueError, TypeError, KeyError) as exc:
        raise DataError("Invalid universe snapshot.") from exc


def ensure_historical_use(
    snapshot: UniverseSnapshot, decision_at: datetime, require_point_in_time: bool = True
) -> None:
    require_utc(decision_at)
    if snapshot.membership_type == "current_snapshot":
        raise DataError("Current constituents cannot be used as historical PIT membership.")
    if require_point_in_time and (
        snapshot.membership_type != "point_in_time" or not snapshot.point_in_time_verified
    ):
        raise DataError("Verified point-in-time membership is required and is not available.")
    if (
        snapshot.available_at is None
        or snapshot.available_at > decision_at
        or snapshot.as_of > decision_at
    ):
        raise DataError("Universe was not available at the historical decision time.")


def _watchlist_io_boundary(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except OSError as exc:
            raise DataError("Watchlist I/O failed; inspect the target before retrying.") from exc

    return wrapped


@_watchlist_io_boundary
def save_watchlist(snapshot: UniverseSnapshot, path: Path, overwrite: bool = False) -> None:
    if snapshot.membership_type != "user_static" or snapshot.synthetic is None:
        raise DataError("Only explicitly labelled custom watchlists can be saved here.")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise DataError("Watchlist exists; use an explicit update.")
    # Updates are deliberate; a temporary complete payload is atomically replaced.
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise DataError("Watchlist update temporary file exists; inspect it before retrying.")
    temporary.write_text(
        json.dumps({"schema_version": 1, "universe": jsonable(snapshot)}, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_watchlist(path: Path) -> UniverseSnapshot:
    try:
        document = json.loads(path.read_text("utf-8"))
        if set(document) != {"schema_version", "universe"} or document["schema_version"] != 1:
            raise DataError("Unknown watchlist schema.")
        snapshot = snapshot_from_dict(document["universe"])
        if (
            snapshot.membership_type != "user_static"
            or snapshot.synthetic is None
            or snapshot.point_in_time_verified
        ):
            raise DataError("A custom watchlist cannot manufacture verified PIT membership.")
        checked = custom_universe(snapshot.assets, snapshot.as_of, snapshot.synthetic)
        return replace(
            checked, available_at=snapshot.available_at, limitations=snapshot.limitations
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise DataError("Cannot read a valid saved watchlist.") from exc


def import_watchlist(path: Path, as_of: datetime, synthetic: bool) -> UniverseSnapshot:
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["market", "exchange", "symbol", "currency"]:
                raise DataError("Watchlist CSV requires market,exchange,symbol,currency.")
            assets = tuple(
                AssetId(**{key: value.strip().upper() for key, value in row.items()})
                for row in reader
            )
        return custom_universe(assets, as_of, synthetic)
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        raise DataError("Invalid custom watchlist CSV.") from exc


@_watchlist_io_boundary
def export_watchlist(snapshot: UniverseSnapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=["market", "exchange", "symbol", "currency"], lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(jsonable(asset) for asset in snapshot.assets)
    except OSError as exc:
        raise DataError("Cannot export watchlist without overwriting an existing file.") from exc


def update_watchlist(
    snapshot: UniverseSnapshot, add: tuple[AssetId, ...], remove: tuple[str, ...], as_of: datetime
) -> UniverseSnapshot:
    if snapshot.membership_type != "user_static" or snapshot.synthetic is None:
        raise DataError("Updates require a custom watchlist.")
    assets = tuple(a for a in (*snapshot.assets, *add) if a.symbol not in set(remove))
    return custom_universe(assets, as_of, snapshot.synthetic)


@dataclass(frozen=True)
class DirectorySnapshot:
    universe: UniverseSnapshot
    content_hash: str
    creation_marker: str
    excluded: tuple[dict, ...]


def parse_nasdaq_directory(
    raw: bytes, retrieved_at: datetime, synthetic: bool = False
) -> DirectorySnapshot:
    require_utc(retrieved_at)
    try:
        lines = raw.decode("utf-8-sig").splitlines()
        if not lines or not lines[-1].startswith("File Creation Time:"):
            raise DataError("Nasdaq directory is incomplete or missing its creation marker.")
        reader = csv.DictReader(io.StringIO("\n".join(lines[:-1])), delimiter="|")
        if not {"Symbol", "Security Name", "Test Issue", "ETF", "NextShares"} <= set(
            reader.fieldnames or ()
        ):
            raise DataError("Nasdaq directory schema changed.")
        assets, excluded = [], []
        seen = set()
        for row in reader:
            symbol = row.get("Symbol", "")
            if (
                row.get("Test Issue") != "N"
                or row.get("ETF") != "N"
                or row.get("NextShares") != "N"
            ):
                excluded.append({"symbol": symbol, "reason": "ETF_TEST_OR_NEXTSHARES"})
                continue
            try:
                asset = AssetId("US", "XNAS", symbol, "USD")
            except DataError:
                excluded.append({"symbol": symbol, "reason": "UNSUPPORTED_IDENTIFIER"})
                continue
            if asset.symbol.startswith("SYN_") != synthetic:
                raise DataError("Real directory and synthetic identities were mixed.")
            if asset in seen:
                raise DataError("Duplicate symbols in Nasdaq source directory.")
            seen.add(asset)
            assets.append(asset)
        universe = UniverseSnapshot(
            "nasdaq-listed-current",
            retrieved_at,
            "current_snapshot",
            tuple(assets),
            "synthetic_directory_fixture" if synthetic else NASDAQ_URL,
            retrieved_at,
            synthetic,
            (
                "Current Nasdaq-listed non-ETF securities, NOT Nasdaq-100 index membership.",
                "Historical membership/delistings unavailable; survivorship bias is NOT solved.",
                "Directory does not prove common-stock-only classification or historical currency.",
                "USD is a request assumption until verified by the price adapter.",
            ),
        )
        return DirectorySnapshot(
            universe, hashlib.sha256(raw).hexdigest(), lines[-1], tuple(excluded)
        )
    except (UnicodeError, csv.Error, TypeError) as exc:
        raise DataError("Cannot parse the Nasdaq directory.") from exc


def fetch_nasdaq_directory(
    policy: RetryPolicy = DEFAULT_RETRY_POLICY, transport=http_get, clock=lambda: datetime.now(UTC)
) -> DirectorySnapshot:
    raw = retry_call(lambda: transport(NASDAQ_URL, policy.timeout), policy)
    return parse_nasdaq_directory(raw, clock())
