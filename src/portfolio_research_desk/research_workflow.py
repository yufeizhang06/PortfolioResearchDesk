"""One auditable pipeline shared by data fetch and combined universe/screening commands."""

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import uuid4

from portfolio_research_desk.data_adapters import (
    HistoryAdapter,
    LocalHistoryAdapter,
    ProviderError,
    YFinanceAdapter,
    write_history,
)
from portfolio_research_desk.data_cache import SnapshotCache, history_key
from portfolio_research_desk.data_contracts import History, history_from_dict, validate_quality
from portfolio_research_desk.domain import UniverseSnapshot, fingerprint, jsonable
from portfolio_research_desk.errors import DataError, ReportError
from portfolio_research_desk.reporting import collect_provenance
from portfolio_research_desk.research_config import ResearchConfig
from portfolio_research_desk.screening import ScreeningResult, screen_universe
from portfolio_research_desk.universe import (
    DirectorySnapshot,
    custom_universe,
    ensure_historical_use,
    fetch_nasdaq_directory,
    load_watchlist,
    parse_nasdaq_directory,
    snapshot_from_dict,
)


@dataclass(frozen=True)
class ResearchRun:
    universe: UniverseSnapshot
    histories: tuple[History, ...]
    quality: tuple[dict, ...]
    screening: ScreeningResult | None
    failures: tuple[dict, ...]
    cache_events: tuple[dict, ...]
    selections: tuple[dict, ...]
    directory: DirectorySnapshot | None
    decision_at: datetime
    status: str


def run_research(
    config: ResearchConfig,
    action: str = "universe",
    adapter: HistoryAdapter | None = None,
    clock=lambda: datetime.now(UTC),
    directory_fetch=fetch_nasdaq_directory,
    refresh: bool = False,
) -> ResearchRun:
    cache = SnapshotCache(config.cache_dir)
    events, selections, failures, histories, qualities = [], [], [], {}, []
    directory = None
    if config.universe_mode == "market":
        directory_kind = "synthetic" if config.directory_fixture else "real"
        if directory_kind != config.expected_kind:
            raise DataError("Market directory and history real/synthetic kinds must agree.")
        key = fingerprint({"type": "nasdaq_directory", "schema": 1, "kind": directory_kind})
        entry = (
            None
            if refresh
            else cache.get(
                key, directory_kind, clock(), timedelta(hours=config.ttl_hours), config.allow_stale
            )
        )
        if entry is not None:
            value = entry.value
            directory = DirectorySnapshot(
                snapshot_from_dict(value["universe"]),
                value["content_hash"],
                value["creation_marker"],
                tuple(value["excluded"]),
            )
            events.append({"type": "directory", "hit": True, "stale": entry.stale})
        else:
            if config.directory_fixture:
                directory = parse_nasdaq_directory(
                    files("portfolio_research_desk")
                    .joinpath("resources/research_directory.txt")
                    .read_bytes(),
                    clock(),
                    True,
                )
            elif config.offline:
                raise DataError("Offline directory cache miss/expiry; no network request was made.")
            else:
                directory = directory_fetch(config.policy)
            cache.put(key, directory_kind, jsonable(directory), clock(), repair=refresh)
            events.append({"type": "directory", "hit": False, "stale": False})
        universe = directory.universe
        if config.assets:
            additions = custom_universe(config.assets, clock(), universe.synthetic)
            universe = replace(
                universe,
                assets=tuple(dict.fromkeys((*universe.assets, *additions.assets))),
                available_at=additions.available_at,
                limitations=universe.limitations
                + ("Includes explicitly supplied custom additions.",),
            )
    elif config.watchlist:
        universe = load_watchlist(config.watchlist)
    else:
        universe = custom_universe(config.assets, clock(), config.expected_kind == "synthetic")
    if universe.synthetic is None or universe.synthetic != (config.expected_kind == "synthetic"):
        raise DataError("Watchlist/data real-synthetic mismatch.")
    requested_include = set(config.include)
    if requested_include - {a.symbol for a in universe.assets}:
        raise DataError("Explicit include symbols are absent from the source universe.")
    selected = []
    for asset in universe.assets:
        reason = (
            "EXCLUDED_BY_USER"
            if asset.symbol in config.exclude
            else "OUTSIDE_INCLUDE"
            if config.include and asset.symbol not in requested_include
            else "SELECTED"
        )
        selections.append({"asset": jsonable(asset), "reason": reason})
        if reason == "SELECTED":
            selected.append(asset)
    universe = replace(universe, assets=tuple(selected))
    if config.require_point_in_time:
        ensure_historical_use(universe, config.as_of or clock())
    need_history = action == "data" or config.rules is not None
    if need_history:
        if len(universe.assets) > config.max_assets:
            raise DataError(
                "Universe exceeds max_assets request budget; select symbols or raise the budget."
            )
        adapter = adapter or (
            LocalHistoryAdapter(config.local_file)
            if config.adapter != "yfinance"
            else YFinanceAdapter(config.cache_dir, config.policy)
        )
        identity = adapter.cache_identity()
        rate_limited = False
        for asset in universe.assets:
            try:
                key = history_key(identity, asset, config.start, config.end, config.expected_kind)
                entry = (
                    None
                    if refresh
                    else cache.get(
                        key,
                        config.expected_kind,
                        clock(),
                        timedelta(hours=config.ttl_hours),
                        config.allow_stale,
                    )
                )
                if entry is not None:
                    history = history_from_dict(entry.value)
                    events.append({"asset": jsonable(asset), "hit": True, "stale": entry.stale})
                else:
                    if config.offline and config.adapter == "yfinance":
                        raise DataError(
                            "Offline history cache miss/expiry; no network request was made."
                        )
                    if rate_limited:
                        raise DataError(
                            "Rate limiting stopped uncached requests; cached assets remain usable."
                        )
                    history = adapter.fetch(asset, config.start, config.end)
                    if history.data_kind != config.expected_kind or any(
                        r.asset != asset or not config.start <= r.session_date < config.end
                        for r in history.rows
                    ):
                        raise DataError(
                            "Adapter kind/identity/date range does not match the request."
                        )
                    cache.put(key, config.expected_kind, jsonable(history), clock(), repair=refresh)
                    events.append({"asset": jsonable(asset), "hit": False, "stale": False})
                if history.data_kind != config.expected_kind or any(
                    r.asset != asset or not config.start <= r.session_date < config.end
                    for r in history.rows
                ):
                    raise DataError(
                        "Cached/adapter history identity, kind or dates do not match the request."
                    )
                quality = validate_quality(history, config.expected_sessions)
                histories[asset] = history
                qualities.append(
                    {
                        "asset": jsonable(asset),
                        "snapshot_hash": history.snapshot_hash,
                        "row_count": len(history.rows),
                        "report": jsonable(quality),
                    }
                )
            except DataError as exc:
                if isinstance(exc, ProviderError) and exc.code in {"RATE_LIMIT", "HTTP_429"}:
                    rate_limited = True
                failures.append(
                    {"asset": jsonable(asset), "reason": str(exc), "status": "DATA_UNAVAILABLE"}
                )
    decision_at = config.as_of or clock()
    screening = (
        screen_universe(universe, histories, config.rules, decision_at, config.expected_sessions)
        if config.rules
        else None
    )
    final_universe = screening.universe if screening else universe
    valid = any(item["report"]["accepted"] for item in qualities)
    errors = any(
        issue["severity"] == "ERROR" for item in qualities for issue in item["report"]["issues"]
    )
    status = (
        "failed" if need_history and not valid else "partial" if failures or errors else "complete"
    )
    return ResearchRun(
        final_universe,
        tuple(histories.values()),
        tuple(qualities),
        screening,
        tuple(failures),
        tuple(events),
        tuple(selections),
        directory,
        decision_at,
        status,
    )


def save_research_run(result: ResearchRun, config: ResearchConfig) -> Path:
    directory = config.output_dir / f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex[:12]}"
    try:
        directory.mkdir(parents=True, exist_ok=False)
        exported = []
        for history in result.histories:
            asset = history.rows[0].asset
            relative = Path("data") / f"prices-{fingerprint(asset)[:16]}.csv"
            write_history(history, directory / relative)
            exported.append(
                {
                    "asset": jsonable(asset),
                    "csv": relative.as_posix(),
                    "metadata": relative.with_suffix(".metadata.json").as_posix(),
                }
            )
        for name, value in (
            ("universe", result.universe),
            ("quality", result.quality),
            ("screening", result.screening),
            ("histories", result.histories),
        ):
            with (directory / f"{name}.json").open("x", encoding="utf-8") as stream:
                json.dump(jsonable(value), stream, indent=2, sort_keys=True, allow_nan=False)
        payload: dict[str, Any] = {
            "schema_version": 2,
            "phase": 2,
            "result": jsonable(result),
            "config": config.snapshot(),
            "config_hash": fingerprint(config.snapshot()),
            "history_hashes": [history.snapshot_hash for history in result.histories],
            "history_files": exported,
            "data_kind": config.expected_kind,
            "status": result.status,
            "provenance": collect_provenance(),
            "historical_pit_verified": False,
            "limitations": [
                "Current membership/delistings are not historical PIT coverage.",
                "Research observations are NOT executable Phase 1 backtest bars.",
            ],
        }
        with (directory / "run.json").open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
        return directory
    except OSError as exc:
        raise ReportError(
            "Research output is incomplete; inspect the reserved run directory."
        ) from exc
