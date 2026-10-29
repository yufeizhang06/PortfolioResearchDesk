"""Thin CLI for offline samples and explicitly reviewed virtual-account operations."""

from datetime import datetime
from pathlib import Path

from portfolio_research_desk.domain import fingerprint
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.paper_config import load_paper_config
from portfolio_research_desk.paper_reporting import read_native, write_native, write_paper_report
from portfolio_research_desk.paper_sample import example_inputs
from portfolio_research_desk.paper_services import simulate_from_snapshot
from portfolio_research_desk.paper_store import PaperAccount
from portfolio_research_desk.product_cli import execute_paper_helper, register_paper_helpers


def register_paper_commands(commands):
    paper = commands.add_parser("paper", help="CAD virtual accounts; never real trades.")
    sub = paper.add_subparsers(dest="paper_command", required=True)
    for name in (
        "init",
        "status",
        "propose",
        "review",
        "simulate",
        "expire",
        "apply",
        "export",
        "demo",
    ):
        p = sub.add_parser(name)
        p.add_argument("--db", type=Path, required=True, help="Local SQLite virtual-account file.")
        if name in {"init", "demo"}:
            p.add_argument("--config", type=Path)
        if name in {"init", "review", "simulate", "expire"}:
            p.add_argument(
                "--at",
                required=name != "simulate",
                help="Explicit UTC ISO timestamp; snapshot simulation may carry its own as_of.",
            )
        if name in {"propose", "apply"}:
            p.add_argument("--input", type=Path, required=True, help="Versioned native paper JSON.")
        if name == "simulate":
            inputs = p.add_mutually_exclusive_group(required=True)
            inputs.add_argument(
                "--input", type=Path, help="Legacy native paper JSON; also requires --at."
            )
            inputs.add_argument(
                "--snapshot", type=Path, help="Readable execution snapshot with explicit as_of."
            )
        if name in {"review", "simulate", "expire"}:
            p.add_argument("--plan-id", required=True)
        if name == "review":
            p.add_argument("--plan-hash", required=True, help="Exact hash from propose/status.")
            group = p.add_mutually_exclusive_group(required=True)
            group.add_argument("--approve", action="store_true")
            group.add_argument("--reject", action="store_true")
            p.add_argument("--reason", default="Human paper-plan review")
        if name == "apply":
            p.add_argument("--event-id", required=True)
        if name in {"export", "demo"}:
            p.add_argument("--output-dir", type=Path, default=Path("outputs/paper-reports"))
            p.add_argument("--run-id")
    sample = sub.add_parser("sample", help="Write fixed synthetic native input files.")
    sample.add_argument("--output-dir", type=Path, required=True)
    register_paper_helpers(sub)


def _at(text):
    try:
        from portfolio_research_desk.domain import require_utc

        stamp = datetime.fromisoformat(text)
        require_utc(stamp)
        return stamp
    except (ValueError, TypeError) as exc:
        raise DataError("Timestamp must be explicit ISO UTC.") from exc


def execute_paper_command(args):
    name = args.paper_command
    if name in {"plan", "summary", "value", "cash-flow", "convert", "validate-snapshot"}:
        return execute_paper_helper(args)
    if name == "sample":
        from portfolio_research_desk.errors import ReportError

        inputs = example_inputs()
        try:
            args.output_dir.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            raise ReportError("Sample directory already exists or is unwritable.") from exc
        decision = {k: inputs[k] for k in ("bundle", "market", "sessions", "decision_at")}
        decision.update(plan_id="sample-plan", top_k=5)
        write_native(args.output_dir / "decision.json", decision)
        write_native(args.output_dir / "execution.json", inputs["execution_market"])
        return {
            "phase": 5,
            "data_kind": "synthetic",
            "sample_directory": str(args.output_dir.resolve()),
        }
    account = PaperAccount(args.db)
    if name == "init":
        config = load_paper_config(args.config)
        account = PaperAccount.create(
            args.db, _at(args.at), config.initial_cash, config.limits, config.costs
        )
        view = account.load()
    elif name == "demo":
        config, inputs = load_paper_config(args.config), example_inputs()
        account = PaperAccount.create(
            args.db, inputs["sessions"][0].open_at, config.initial_cash, config.limits, config.costs
        )
        view = account.propose(
            inputs["bundle"],
            inputs["market"],
            inputs["sessions"],
            inputs["decision_at"],
            "synthetic-demo",
            config.top_k,
        )
        plan = view.plans["synthetic-demo"].plan
        account.review(
            plan.plan_id,
            inputs["review_at"],
            fingerprint(plan),
            True,
            "SCRIPTED SYNTHETIC DEMO REVIEW; not live human authorization",
        )
        view = account.execute(plan.plan_id, inputs["execution_at"], inputs["execution_market"])
    elif name == "propose":
        inputs = read_native(args.input)
        if not isinstance(inputs, dict) or set(inputs) - {
            "bundle",
            "market",
            "sessions",
            "decision_at",
            "plan_id",
            "top_k",
            "target",
        }:
            raise DataError("Invalid paper proposal inputs.")
        if not {"bundle", "market", "sessions", "decision_at", "plan_id"} <= inputs.keys():
            raise DataError("Missing paper proposal inputs.")
        view = account.propose(**inputs)
    elif name == "review":
        view = account.review(args.plan_id, _at(args.at), args.plan_hash, args.approve, args.reason)
    elif name == "simulate":
        if args.snapshot:
            return simulate_from_snapshot(
                account, args.snapshot, args.plan_id, _at(args.at) if args.at else None
            )
        if args.at is None:
            raise DataError(
                "Native --input requires --at; readable --snapshot includes its own as_of."
            )
        view = account.execute(args.plan_id, _at(args.at), read_native(args.input))
    elif name == "expire":
        view = account.expire(args.plan_id, _at(args.at))
    elif name == "apply":
        command = read_native(args.input)
        if (
            not isinstance(command, dict)
            or not isinstance(command.get("kind"), str)
            or command.get("kind")
            not in {
                "CASH",
                "CONVERT",
                "ACTION",
                "VALUE",
            }
        ):
            raise DataError("paper apply only accepts CASH/CONVERT/ACTION/VALUE events.")
        view = account.append(args.event_id, command)
    else:
        view = account.load()
    result = {
        "phase": 5,
        "mode": "paper",
        "base_currency": "CAD",
        "credible_real_market_oos": False,
        "state": view.state,
        "event_count": view.event_count,
        "head_hash": view.head_hash,
        "plans": {
            k: {
                "status": v.status,
                "plan_hash": fingerprint(v.plan),
                "plan": v.plan,
                "reason": v.reason,
                "fills": v.fills,
            }
            for k, v in view.plans.items()
        },
    }
    if name in {"export", "demo"}:
        directory = write_paper_report(account, args.output_dir, args.run_id)
        result["report_directory"] = str(directory.resolve())
    return result
