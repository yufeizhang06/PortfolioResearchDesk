"""SQLite lookup plus immutable, checksummed JSON snapshots in real/synthetic namespaces."""

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any
from uuid import uuid4

from portfolio_research_desk.domain import fingerprint, jsonable, require_utc
from portfolio_research_desk.errors import DataError


@dataclass(frozen=True)
class CacheEntry:
    value: dict[str, Any]
    created_at: datetime
    stale: bool


def _storage_boundary(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except (OSError, sqlite3.Error) as exc:
            raise DataError("Local cache I/O/index failure; no silent fallback.") from exc

    return wrapped


class SnapshotCache:
    @_storage_boundary
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.index = root / "index.sqlite"
        with sqlite3.connect(self.index, timeout=10) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS entries (key TEXT NOT NULL, kind TEXT NOT NULL, "
                "hash TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(key,kind))"
            )
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='snapshots'"
            ).fetchone():
                connection.execute(
                    "INSERT OR IGNORE INTO entries SELECT key,kind,hash,created_at FROM snapshots"
                )

    @_storage_boundary
    def get(
        self, key: str, kind: str, now: datetime, ttl: timedelta, allow_stale: bool = False
    ) -> CacheEntry | None:
        require_utc(now)
        if kind not in {"real", "synthetic"} or ttl.total_seconds() <= 0:
            raise DataError("Invalid cache namespace or TTL.")
        with sqlite3.connect(self.index, timeout=10) as connection:
            row = connection.execute(
                "SELECT hash,created_at FROM entries WHERE key=? AND kind=?", (key, kind)
            ).fetchone()
        if row is None:
            return None
        digest, created = row
        try:
            stamp = datetime.fromisoformat(created)
            require_utc(stamp)
            if not re.fullmatch(r"[0-9a-f]{64}", digest) or stamp > now:
                raise DataError("Invalid cache snapshot identity or future creation time.")
            stale = now - stamp > ttl
            if stale and not allow_stale:
                return None
            path = self.root / "snapshots" / kind / f"{digest}.json"
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != digest:
                raise DataError("Cache checksum mismatch; refresh from the original source.")
            value = json.loads(raw)
            if value["kind"] != kind:
                raise DataError("Cache real/synthetic namespace mismatch.")
            return CacheEntry(value["payload"], stamp, stale)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise DataError("Unreadable cache snapshot; no silent fallback.") from exc

    @_storage_boundary
    def put(
        self,
        key: str,
        kind: str,
        value: dict[str, Any],
        created_at: datetime | None = None,
        repair: bool = False,
    ) -> str:
        if kind not in {"real", "synthetic"}:
            raise DataError("Unknown cache namespace.")
        stamp = created_at or datetime.now(UTC)
        require_utc(stamp)
        raw = json.dumps(
            jsonable({"kind": kind, "payload": value}),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        folder = self.root / "snapshots" / kind
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{digest}.json"
        if path.exists():
            if path.read_bytes() != raw:
                if not repair:
                    raise DataError(
                        "An existing cache snapshot is corrupt; explicit refresh required."
                    )
                path.rename(path.with_suffix(f".corrupt-{uuid4().hex}"))
        if not path.exists():
            # Exclusive creation; readers only discover it after the SQLite transaction commits.
            try:
                with path.open("xb") as output:
                    output.write(raw)
            except FileExistsError:
                if path.read_bytes() != raw:
                    raise DataError(
                        "Concurrent cache write did not match the immutable snapshot."
                    ) from None
        with sqlite3.connect(self.index, timeout=10) as connection:
            connection.execute(
                "INSERT INTO entries VALUES (?,?,?,?) ON CONFLICT(key,kind) DO UPDATE SET "
                "hash=excluded.hash,created_at=excluded.created_at",
                (key, kind, digest, stamp.isoformat()),
            )
        return digest


def history_key(identity: dict, asset: object, start: object, end: object, kind: str) -> str:
    return fingerprint(
        {
            "type": "history",
            "schema": 1,
            "adapter": identity,
            "asset": asset,
            "start_inclusive": start,
            "end_exclusive": end,
            "kind": kind,
        }
    )
