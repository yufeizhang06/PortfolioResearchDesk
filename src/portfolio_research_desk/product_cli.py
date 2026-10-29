"""Product command registration; all work delegates to reusable services."""

from dataclasses import replace
from pathlib import Path

from portfolio_research_desk.delivery_reports import verify_workflow_report
from portfolio_research_desk.diagnostics import inspect_environment
from portfolio_research_desk.fx import FXBook, load_fx_csv
from portfolio_research_desk.paper_inputs import decimal_field, load_paper_input, stamp
from portfolio_research_desk.paper_services import (
    account_summary,
    propose_from_snapshot,
    value_from_snapshot,
)
from portfolio_research_desk.paper_store import PaperAccount
from portfolio_research_desk.product_workflow import run_workflow
from portfolio_research_desk.workflow_config import load_workflow_config
from portfolio_research_desk.workspace import create_workspace


def register_product_commands(commands):
    doctor = commands.add_parser(
        "doctor",
        help="Offline Python/package/optional-extra diagnostics; no installation or data download.",
    )
    doctor.add_argument("--require", choices=("data", "factors", "ml"), action="append", default=[])
    workspace = commands.add_parser(
        "workspace", help="Create an editable local workspace with safe synthetic examples."
    )
    sub = workspace.add_subparsers(dest="workspace_command", required=True)
    init = sub.add_parser(
        "init", help="Create a new directory; existing workspaces are never overwritten."
    )
    init.add_argument("--directory", type=Path, required=True)
    workflow = commands.add_parser(
        "workflow", help="Unified offline universe/research/backtest/CAD paper delivery."
    )
    sub = workflow.add_subparsers(dest="workflow_command", required=True)
    run = sub.add_parser(
        "run", help="Run the synthetic integrated demo and write an HTML report index."
    )
    run.add_argument("--config", type=Path)
    run.add_argument("--output-dir", type=Path)
    run.add_argument("--run-id")
    run.add_argument(
        "--with-factors",
        action="store_true",
        help="Include separate ex-post factor diagnostics; requires factors extra.",
    )
    run.add_argument(
        "--with-ml",
        action="store_true",
        help="Include synthetic OOS validation and a pending CAD preview; requires ml extra.",
    )
    check = sub.add_parser(
        "check", help="Verify every immutable run artifact hash and path without network access."
    )
    check.add_argument("--directory", type=Path, required=True)


def execute_product_command(args):
    if args.command == "doctor":
        result = inspect_environment(tuple(args.require))
        return result, 0 if result["status"] == "ready" else 2
    if args.command == "workspace":
        return create_workspace(args.directory), 0
    if args.workflow_command == "check":
        return verify_workflow_report(args.directory), 0
    config = load_workflow_config(args.config)
    config = replace(
        config,
        include_factors=config.include_factors or args.with_factors,
        include_ml=config.include_ml or args.with_ml,
        output_dir=args.output_dir.resolve() if args.output_dir else config.output_dir,
    )
    return run_workflow(config, args.run_id), 0


def register_paper_helpers(sub):
    for name in ("plan", "summary", "value", "cash-flow", "convert", "validate-snapshot"):
        p = sub.add_parser(
            name,
            help={
                "plan": "Plan from readable JSON; stays pending human review.",
                "summary": "Compact account, recorded NAV freshness and pending plans.",
                "value": "Record a valuation from readable JSON.",
                "cash-flow": "Record a signed external flow with an idempotent event ID.",
                "convert": "Explicit CAD/USD cash conversion with recorded FX costs.",
                "validate-snapshot": "Validate readable input without changing an account.",
            }[name],
        )
        if name != "validate-snapshot":
            p.add_argument("--db", type=Path, required=True)
        if name in {"plan", "value", "validate-snapshot"}:
            p.add_argument("--snapshot", type=Path, required=True)
        if name == "plan":
            p.add_argument("--plan-id", required=True)
            p.add_argument("--top-k", type=int, default=2)
        if name in {"value", "cash-flow", "convert"}:
            p.add_argument("--event-id", required=True)
        if name in {"cash-flow", "convert"}:
            p.add_argument("--at", required=True)
            p.add_argument("--fx-csv", type=Path, required=name == "convert")
        if name == "cash-flow":
            p.add_argument("--currency", choices=("CAD", "USD"), required=True)
            p.add_argument(
                "--amount", required=True, help="Signed decimal amount in the named currency."
            )
        if name == "convert":
            p.add_argument("--source", choices=("CAD", "USD"), required=True)
            p.add_argument(
                "--usd-amount", required=True, help="USD cents to buy with CAD or to sell for CAD."
            )


def execute_paper_helper(args):
    name = args.paper_command
    if name == "validate-snapshot":
        result = load_paper_input(args.snapshot)
        return {
            "phase": 6,
            "status": "valid",
            "purpose": result.purpose,
            "as_of": result.as_of,
            "data_kind": result.data_kind,
            "price_count": len(result.market.quotes),
            "credible_real_market_oos": False,
        }
    account = PaperAccount(args.db)
    if name == "summary":
        return account_summary(account)
    if name == "plan":
        return propose_from_snapshot(account, args.snapshot, args.plan_id, args.top_k)
    if name == "value":
        return value_from_snapshot(account, args.snapshot, args.event_id)
    at = stamp(args.at, "--at")
    fx = load_fx_csv(args.fx_csv) if args.fx_csv else FXBook()
    if name == "cash-flow":
        command = dict(
            kind="CASH",
            at=at,
            currency=args.currency,
            amount=decimal_field(args.amount, "--amount"),
            fx=fx,
        )
    else:
        command = dict(
            kind="CONVERT",
            at=at,
            source=args.source,
            amount=decimal_field(args.usd_amount, "--usd-amount"),
            fx=fx,
        )
    account.append(args.event_id, command)
    return account_summary(account)
