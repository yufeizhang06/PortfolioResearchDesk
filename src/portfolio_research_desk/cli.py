"""Small CLI boundary: argparse -> configuration -> offline sample service."""

import argparse
import json
import logging
from pathlib import Path

from portfolio_research_desk import __version__
from portfolio_research_desk.backtest import run_backtest
from portfolio_research_desk.backtest_config import load_backtest_config
from portfolio_research_desk.config import load_config
from portfolio_research_desk.data_cli import execute_data_command, register_data_commands
from portfolio_research_desk.domain import jsonable
from portfolio_research_desk.errors import ProjectError
from portfolio_research_desk.reporting import write_report
from portfolio_research_desk.research_config import load_research_config
from portfolio_research_desk.sample import summarize_sample

_LOG = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Print JSON to stdout, diagnostic logs to stderr, expected errors as exit 2."""
    parser = argparse.ArgumentParser(
        prog="prd",
        description="PortfolioResearchDesk: Phase 0 inspection; Phase 1 simulation; Phase 2 data.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    config = commands.add_parser("config", help="Configuration utilities.")
    config_commands = config.add_subparsers(dest="config_command", required=True)
    validate = config_commands.add_parser(
        "validate", help="Validate Phase 0 TOML and print snapshot."
    )
    validate.add_argument(
        "--config", type=Path, help="UTF-8 TOML file; default: packaged offline config."
    )
    validate.add_argument(
        "--kind",
        choices=("offline", "backtest", "research"),
        default="offline",
        help="Configuration schema; default: offline (Phase 0).",
    )
    demo = commands.add_parser("demo", help="Summarize bundled synthetic prices; no trading.")
    demo.add_argument(
        "--config", type=Path, help="UTF-8 TOML file; default: packaged offline config."
    )
    backtest = commands.add_parser(
        "backtest", help="Synthetic USD historical execution simulation."
    )
    backtest_commands = backtest.add_subparsers(dest="backtest_command", required=True)
    run = backtest_commands.add_parser(
        "run", help="Run an offline custom-universe momentum backtest."
    )
    run.add_argument("--config", type=Path, help="Phase 1 TOML; default: packaged backtest config.")
    run.add_argument(
        "--output-dir", type=Path, default=Path("outputs/runs"), help="Run bundle parent directory."
    )
    run.add_argument(
        "--run-id", help="Optional unique run identifier; existing runs are never overwritten."
    )
    register_data_commands(commands)
    args = parser.parse_args(argv)
    try:
        if args.command in {"data", "universe"}:
            logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
            payload, exit_code = execute_data_command(args)
            print(json.dumps(jsonable(payload), indent=2, sort_keys=True, ensure_ascii=True))
            return exit_code
        if args.command == "config" and args.kind == "research":
            print(
                json.dumps(
                    {"phase": 2, "config": load_research_config(args.config).snapshot()},
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        is_backtest = args.command == "backtest" or (
            args.command == "config" and args.kind == "backtest"
        )
        settings = load_backtest_config(args.config) if is_backtest else load_config(args.config)
        logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s: %(message)s")
        payload: dict[str, object] = {
            "phase": 1 if is_backtest else 0,
            "config": settings.snapshot(),
        }
        if args.command == "backtest":
            result = run_backtest(settings)
            directory = write_report(result, args.output_dir, args.run_id)
            payload.update(
                run_id=directory.name,
                report_directory=str(directory.resolve()),
                metrics=jsonable(result.metrics),
                warnings=result.warnings,
            )
            _LOG.info(
                "Completed synthetic USD backtest: %d fills; report: %s",
                len(result.fills),
                directory,
            )
        if args.command == "demo":
            payload["sample"] = summarize_sample()
            _LOG.info("Loaded packaged synthetic sample (Phase 0 metadata only).")
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
    except ProjectError as exc:
        parser.exit(2, f"prd: error: {exc}\n")
    return 0
