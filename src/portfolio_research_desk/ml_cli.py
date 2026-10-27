"""Thin Phase 4 CLI boundary."""

from pathlib import Path

from portfolio_research_desk.ml_config import load_ml_config
from portfolio_research_desk.ml_reporting import save_ml_report
from portfolio_research_desk.ml_workflow import run_ml_experiment


def register_ml_commands(commands):
    ml = commands.add_parser("ml", help="Synthetic leak-safe ML and walk-forward validation.")
    sub = ml.add_subparsers(dest="ml_command", required=True)
    run = sub.add_parser("run", help="Compare nested development folds and frozen final holdout.")
    run.add_argument("--config", type=Path)
    run.add_argument("--output-dir", type=Path, default=Path("outputs/ml"))
    run.add_argument("--run-id")


def execute_ml_command(args):
    result = run_ml_experiment(load_ml_config(args.config))
    directory = save_ml_report(result, args.output_dir, args.run_id)
    return {
        "phase": 4,
        "status": "complete",
        "data_kind": "synthetic",
        "credible_real_market_oos": False,
        "report_directory": str(directory.resolve()),
        "selected_model": result.frozen_plan["selected_model"],
        "metrics": result.metrics,
        "warnings": result.warnings,
    }
