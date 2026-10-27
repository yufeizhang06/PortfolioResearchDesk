"""Thin CLI boundary for the reusable factor research workflow."""

from dataclasses import replace
from pathlib import Path

from portfolio_research_desk.factor_config import load_factor_config
from portfolio_research_desk.factor_reporting import save_factor_report
from portfolio_research_desk.factor_workflow import run_factor_research


def register_factor_commands(commands):
    research = commands.add_parser("research", help="Descriptive factor research and diagnostics.")
    sub = research.add_subparsers(dest="research_command", required=True)
    run = sub.add_parser("run", help="Run common-sample FF3/Carhart FF4 and trailing exposures.")
    run.add_argument(
        "--config", type=Path, help="Phase 3 TOML; default: synthetic offline research."
    )
    run.add_argument("--output-dir", type=Path)
    run.add_argument("--run-id")
    run.add_argument(
        "--offline", action="store_true", help="Block source requests; use valid cache/local files."
    )
    run.add_argument(
        "--allow-stale", action="store_true", help="Explicit stale factor/price cache permission."
    )


def execute_factor_command(args):
    config = load_factor_config(args.config)
    config = replace(
        config,
        offline=config.offline or args.offline,
        allow_stale=config.allow_stale or args.allow_stale,
        output_dir=args.output_dir.resolve() if args.output_dir else config.output_dir,
    )
    result = run_factor_research(config)
    directory = save_factor_report(result, config.output_dir, args.run_id)
    return {
        "phase": 3,
        "status": result.status,
        "data_kind": config.expected_kind,
        "frequency": config.frequency,
        "nobs": len(result.sample.rows),
        "report_directory": str(directory.resolve()),
        "historical_signal_eligible": False,
        "warnings": result.warnings,
    }, 2 if result.status == "failed" else 0
