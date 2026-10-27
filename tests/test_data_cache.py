import json
from datetime import UTC, datetime, timedelta

import pytest

from portfolio_research_desk.data_cache import SnapshotCache, history_key
from portfolio_research_desk.errors import DataError


def test_cache_identity_separates_kind_source_asset_and_dates(tmp_path):
    key = history_key({"adapter": "csv", "v": 1}, "A", "start", "end", "real")
    assert (
        len(
            {
                key,
                history_key({"adapter": "csv", "v": 2}, "A", "start", "end", "real"),
                history_key({"adapter": "csv", "v": 1}, "B", "start", "end", "real"),
                history_key({"adapter": "csv", "v": 1}, "A", "start", "later", "real"),
                history_key({"adapter": "csv", "v": 1}, "A", "start", "end", "synthetic"),
            }
        )
        == 5
    )


def test_cache_hit_expiry_explicit_stale_and_kind_isolation(tmp_path):
    cache = SnapshotCache(tmp_path)
    stamp = datetime(2024, 1, 1, tzinfo=UTC)
    digest = cache.put("key", "real", {"observed": 1}, stamp)
    assert cache.get("key", "real", stamp, timedelta(hours=1)).value == {"observed": 1}
    assert cache.get("key", "synthetic", stamp, timedelta(hours=1)) is None
    later = stamp + timedelta(hours=2)
    assert cache.get("key", "real", later, timedelta(hours=1)) is None
    assert cache.get("key", "real", later, timedelta(hours=1), True).stale
    assert (tmp_path / f"snapshots/real/{digest}.json").is_file()


def test_corrupt_snapshot_never_silently_passes(tmp_path):
    cache = SnapshotCache(tmp_path)
    stamp = datetime(2024, 1, 1, tzinfo=UTC)
    digest = cache.put("key", "synthetic", {"a": 1}, stamp)
    path = tmp_path / f"snapshots/synthetic/{digest}.json"
    path.write_text(json.dumps({"kind": "real", "payload": {"a": 99}}))
    with pytest.raises(DataError, match="checksum"):
        cache.get("key", "synthetic", stamp, timedelta(hours=1))
    with pytest.raises(DataError, match="corrupt"):
        cache.put("key", "synthetic", {"a": 1}, stamp)


def test_future_cache_timestamp_and_invalid_namespace_rejected(tmp_path):
    cache = SnapshotCache(tmp_path)
    stamp = datetime(2024, 1, 1, tzinfo=UTC)
    cache.put("key", "real", {"a": 1}, stamp)
    with pytest.raises(DataError):
        cache.get("key", "real", stamp - timedelta(seconds=1), timedelta(hours=1))
    with pytest.raises(DataError):
        cache.put("key", "mixed", {})


def test_same_lookup_key_has_independent_real_and_synthetic_entries(tmp_path):
    cache = SnapshotCache(tmp_path)
    stamp = datetime(2024, 1, 1, tzinfo=UTC)
    cache.put("shared", "real", {"real": 1}, stamp)
    cache.put("shared", "synthetic", {"synthetic": 1}, stamp)
    assert cache.get("shared", "real", stamp, timedelta(hours=1)).value == {"real": 1}
    assert cache.get("shared", "synthetic", stamp, timedelta(hours=1)).value == {"synthetic": 1}


def test_explicit_refresh_can_repair_with_corrupt_evidence_preserved(tmp_path):
    cache = SnapshotCache(tmp_path)
    stamp = datetime(2024, 1, 1, tzinfo=UTC)
    digest = cache.put("key", "real", {"a": 1}, stamp)
    path = tmp_path / f"snapshots/real/{digest}.json"
    path.write_text("damaged")
    cache.put("key", "real", {"a": 1}, stamp, repair=True)
    assert cache.get("key", "real", stamp, timedelta(hours=1)).value == {"a": 1}
    assert len(list(path.parent.glob("*.corrupt-*"))) == 1


def test_invalid_sqlite_index_is_a_clear_application_error(tmp_path):
    (tmp_path / "index.sqlite").write_bytes(b"not a SQLite database")
    with pytest.raises(DataError, match="cache I/O"):
        SnapshotCache(tmp_path)
