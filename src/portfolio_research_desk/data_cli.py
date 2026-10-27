"""CLI registration and orchestration for Phase 2; no research logic in argparse."""

import argparse
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from portfolio_research_desk.data_adapters import LocalHistoryAdapter, write_history
from portfolio_research_desk.data_contracts import validate_quality
from portfolio_research_desk.domain import AssetId, jsonable
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.research_config import load_research_config
from portfolio_research_desk.research_workflow import run_research, save_research_run
from portfolio_research_desk.universe import (
    export_watchlist,
    import_watchlist,
    load_watchlist,
    save_watchlist,
    update_watchlist,
)


def register_data_commands(commands) -> None:
    universe = commands.add_parser("universe", help="Custom/market/screened universe workflow.")
    sub = universe.add_subparsers(dest="universe_command", required=True)
    build = sub.add_parser(
        "build", help="Build a provenance-bearing universe with optional screening."
    )
    data = commands.add_parser(
        "data", help="Real/synthetic data acquisition, quality and conversion."
    )
    data_sub = data.add_subparsers(dest="data_command", required=True)
    fetch = data_sub.add_parser("fetch", help="Fetch normalized histories and quality reports.")
    for parser in (build, fetch):
        parser.add_argument(
            "--config",
            type=Path,
            help="Phase 2 TOML; default is an explicit offline synthetic fixture.",
        )
        parser.add_argument("--output-dir", type=Path)
        parser.add_argument(
            "--offline",
            action="store_true",
            help="Never request remote data; cache/local files only.",
        )
        parser.add_argument(
            "--refresh", action="store_true", help="Explicitly bypass prior snapshots."
        )
        parser.add_argument(
            "--allow-stale",
            action="store_true",
            help="Explicit stale-cache use, recorded in the report.",
        )
    check = data_sub.add_parser("check", help="Inspect a native local CSV/Parquet without network.")
    convert = data_sub.add_parser(
        "convert", help="Convert native CSV/Parquet preserving provenance."
    )
    for parser in (check, convert):
        parser.add_argument("--input", type=Path, required=True)
        parser.add_argument("--kind", choices=("real", "synthetic"), required=True)
    convert.add_argument("--output", type=Path, required=True)
    watchlist = sub.add_parser("watchlist", help="Persist/import/export/update custom lists.")
    watch_sub = watchlist.add_subparsers(dest="watchlist_command", required=True)
    importing = watch_sub.add_parser("import", help="Import explicit identity CSV and deduplicate.")
    exporting = watch_sub.add_parser("export", help="Export saved watchlist to identity CSV.")
    updating = watch_sub.add_parser(
        "update", help="Explicitly add/remove assets from a saved watchlist."
    )
    for parser in (importing, exporting, updating):
        parser.add_argument("--input", type=Path, required=True)
        parser.add_argument("--output", type=Path, required=True)
    importing.add_argument("--kind", choices=("real", "synthetic"), required=True)
    updating.add_argument("--add", action="append", default=[], metavar="US:XNAS:AAPL:USD")
    updating.add_argument("--remove", action="append", default=[])


def execute_data_command(args: argparse.Namespace) -> tuple[dict, int]:
    if args.command == "universe" and args.universe_command == "watchlist":
        if args.watchlist_command == "import":
            snapshot = import_watchlist(args.input, datetime.now(UTC), args.kind == "synthetic")
            save_watchlist(snapshot, args.output)
        elif args.watchlist_command == "export":
            snapshot = load_watchlist(args.input)
            export_watchlist(snapshot, args.output)
        else:
            snapshot = load_watchlist(args.input)
            try:
                additions = tuple(
                    AssetId(*(p.strip().upper() for p in value.split(":"))) for value in args.add
                )
            except TypeError as exc:
                raise DataError("--add requires MARKET:EXCHANGE:SYMBOL:CURRENCY.") from exc
            snapshot = update_watchlist(
                snapshot,
                additions,
                tuple(s.strip().upper() for s in args.remove),
                datetime.now(UTC),
            )
            save_watchlist(
                snapshot, args.output, overwrite=args.input.resolve() == args.output.resolve()
            )
        return {"phase": 2, "universe": jsonable(snapshot), "output": str(args.output.resolve())}, 0
    if args.command == "data" and args.data_command in {"check", "convert"}:
        history = LocalHistoryAdapter(args.input).read()
        if history.data_kind != args.kind:
            raise DataError("Local data kind does not match --kind.")
        if args.data_command == "convert":
            write_history(history, args.output)
        report = validate_quality(history)
        return {
            "phase": 2,
            "data_kind": history.data_kind,
            "snapshot_hash": history.snapshot_hash,
            "row_count": len(history.rows),
            "quality": jsonable(report),
        }, 0 if report.accepted else 2
    config = load_research_config(args.config)
    config = replace(
        config,
        offline=config.offline or args.offline,
        allow_stale=config.allow_stale or args.allow_stale,
        output_dir=args.output_dir.resolve() if args.output_dir else config.output_dir,
    )
    result = run_research(
        config, "data" if args.command == "data" else "universe", refresh=args.refresh
    )
    directory = save_research_run(result, config)
    return {
        "phase": 2,
        "status": result.status,
        "data_kind": config.expected_kind,
        "universe": jsonable(result.universe),
        "history_count": len(result.histories),
        "failures": result.failures,
        "cache_events": result.cache_events,
        "report_directory": str(directory.resolve()),
        "historical_pit_verified": False,
    }, 2 if result.status == "failed" else 0
