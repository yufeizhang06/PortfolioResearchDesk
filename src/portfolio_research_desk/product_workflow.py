"""Offline product orchestration; engines retain their data/time/accounting contracts."""

import csv
import html
from dataclasses import replace
from datetime import timedelta
from importlib.resources import files

from portfolio_research_desk.backtest import run_backtest
from portfolio_research_desk.backtest_config import BacktestConfig
from portfolio_research_desk.delivery_reports import bundle_hashes, reserve_run, write_json
from portfolio_research_desk.diagnostics import require_workflow_extras
from portfolio_research_desk.domain import fingerprint
from portfolio_research_desk.errors import ExecutionError, ReportError
from portfolio_research_desk.paper_domain import CADState
from portfolio_research_desk.paper_reporting import write_paper_report
from portfolio_research_desk.paper_services import account_summary, plan_summary
from portfolio_research_desk.paper_store import PaperAccount
from portfolio_research_desk.portfolio_risk import MarketSnapshot
from portfolio_research_desk.reporting import collect_provenance, write_report
from portfolio_research_desk.universe import (
    export_watchlist,
    import_watchlist,
    load_watchlist,
    save_watchlist,
)
from portfolio_research_desk.workflow_fixtures import delivery_inputs, paper_documents


def _ml_preview(result, directory, initial_cash_cad):
    """Adapt a frozen selected model to an unexecuted CAD proposal, never factors."""
    from decimal import Decimal

    from portfolio_research_desk.fx import FXBook, FXRate
    from portfolio_research_desk.paper_domain import Quote, Sector
    from portfolio_research_desk.portfolio_risk import RiskLimits
    from portfolio_research_desk.rebalancing import bundle_from_ml_predictions, propose_rebalance
    from portfolio_research_desk.universe import custom_universe

    model = result.frozen_plan["selected_model"]
    records = [r for r in result.predictions if r["model"] == model and r["stage"] == "holdout"]
    at = min(r["decision_at"] for r in records)
    assets = tuple(sorted({r["asset"] for r in records if r["decision_at"] == at}))
    universe = custom_universe(assets, result.dataset.sessions[0].open_at, True)
    bundle = bundle_from_ml_predictions(records, universe, at, model, data_kind="synthetic")
    bars = tuple(b for b in result.dataset.bars if b.session_date == at.date())
    sectors = tuple(
        Sector(a, f"Synthetic sector {i}", universe.as_of, universe.as_of)
        for i, a in enumerate(assets)
    )
    market = MarketSnapshot(
        tuple(
            Quote(b.asset, b.observation_end, b.available_at, b.close, volume=b.volume)
            for b in bars
        ),
        FXBook((FXRate(at, at, Decimal("1.35"), "synthetic_ml_preview_fx", True),)),
        sectors,
    )
    state = CADState(
        result.dataset.sessions[0].open_at, (("CAD", initial_cash_cad), ("USD", Decimal("0.00")))
    )
    plan = propose_rebalance(
        state, bundle, market, result.dataset.sessions, at, "ml-preview", RiskLimits(), top_k=2
    )
    payload = {
        "status": "PENDING_REVIEW",
        "mode": "paper_preview",
        "data_kind": "synthetic",
        "credible_real_market_oos": False,
        "source": "development-selected model; holdout metrics do not select it",
        "selected_model": model,
        "plan": plan,
        "plan_hash": fingerprint(plan),
        "fills": [],
    }
    write_json(directory / "ml-paper-preview.json", payload)
    return {"status": "pending_review", "file": "ml-paper-preview.json", "selected_model": model}


def run_workflow(config, run_id=None):
    require_workflow_extras(config)  # Missing/broken extras cannot leave a fake completed run.
    directory = reserve_run(config.output_dir, run_id)
    try:
        write_json(directory / "config.json", config.snapshot())
        write_json(directory / "provenance.json", collect_provenance())
        inputs = delivery_inputs()
        dataset, bundle = inputs["dataset"], inputs["bundle"]
        # Exercise the same import/save/load/export services exposed by universe CLI.
        with (directory / "watchlist.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("market", "exchange", "symbol", "currency"))
            writer.writerows(
                (a.market, a.exchange, a.symbol, a.currency) for a in bundle.universe.assets
            )
        universe = import_watchlist(directory / "watchlist.csv", bundle.universe.as_of, True)
        save_watchlist(universe, directory / "watchlist.json")
        recovered_universe = load_watchlist(directory / "watchlist.json")
        export_watchlist(recovered_universe, directory / "watchlist-export.csv")
        if recovered_universe.assets != bundle.universe.assets:
            raise ExecutionError("Imported universe identities did not recover exactly.")
        bundle = replace(bundle, universe=recovered_universe)
        write_json(
            directory / "research.json",
            {
                "data_kind": "synthetic",
                "universe": universe,
                "signals": bundle.signals,
                "source": "past-only 1-session momentum on shared fixture bars",
                "decision_at": inputs["decision_at"],
                "input_dataset_hash": dataset.data_hash,
                "credible_real_market_oos": False,
            },
        )
        for name, document in paper_documents().items():
            write_json(directory / (name + ".json"), document)
        historical = run_backtest(BacktestConfig(), dataset)
        write_report(historical, directory / "historical-usd", "baseline")
        components = {
            "universe": {"status": "complete", "file": "watchlist.json"},
            "research": {"status": "complete", "file": "research.json"},
            "historical_usd": {
                "status": "complete",
                "file": "historical-usd/baseline/report.html",
                "scope": (
                    "separate USD simulation on the same synthetic price fixture; "
                    "not CAD performance"
                ),
            },
        }
        account = PaperAccount.create(
            directory / "account.sqlite3", dataset.sessions[0].open_at, config.initial_cash_cad
        )
        pending = account.propose(
            bundle,
            inputs["decision"],
            inputs["sessions"],
            inputs["decision_at"],
            "workflow",
            config.top_k,
        )
        plan = pending.plans["workflow"].plan
        write_json(directory / "review-plan.json", plan_summary(pending.plans["workflow"]))
        account.review(
            plan.plan_id,
            inputs["decision_at"] + timedelta(seconds=30),
            fingerprint(plan),
            True,
            "SCRIPTED SYNTHETIC WORKFLOW REVIEW ONLY; no live human investment approval",
        )
        executed = account.execute(plan.plan_id, inputs["execution_at"], inputs["opening"])
        if executed.plans[plan.plan_id].status != "SIMULATED":
            raise ExecutionError(
                "Synthetic workflow execution rejected: " + executed.plans[plan.plan_id].reason
            )
        if account.execute(plan.plan_id, inputs["execution_at"], inputs["opening"]) != executed:
            raise ExecutionError("Repeated workflow simulation changed account state.")
        valued = account.append(
            "closing-valuation",
            dict(kind="VALUE", at=inputs["valuation_at"], market=inputs["closing"]),
        )
        if PaperAccount(account.path).load() != valued:
            raise ExecutionError("Paper restart recovery differs from the saved account.")
        paper_report = write_paper_report(account, directory / "paper", "account")
        summary = account_summary(account)
        write_json(directory / "account-summary.json", summary)
        components["paper_cad"] = {
            "status": "complete",
            "file": paper_report.relative_to(directory).as_posix() + "/report.html",
            "opening_nav_cad": executed.valuations[-1].nav_cad,
            "ending_nav_cad": valued.valuations[-1].nav_cad,
            "cash": valued.state.cash,
            "risk_violations": valued.valuations[-1].violations,
            "fill_count": len(valued.plans[plan.plan_id].fills),
            "restart_identical": True,
            "retry_identical": True,
        }
        if config.include_factors:
            from portfolio_research_desk.factor_config import load_factor_config
            from portfolio_research_desk.factor_reporting import save_factor_report
            from portfolio_research_desk.factor_workflow import run_factor_research

            factor_result = run_factor_research(load_factor_config())
            if factor_result.status != "complete":
                raise ExecutionError("Requested synthetic factor diagnostics did not complete.")
            report = save_factor_report(factor_result, directory / "factors", "diagnostic")
            components["factors"] = {
                "status": factor_result.status,
                "file": report.relative_to(directory).as_posix() + "/report.html",
                "scope": (
                    "independent known-answer factor fixture; ex-post diagnostic, "
                    "not a trading input"
                ),
            }
        else:
            components["factors"] = {"status": "not_requested", "enable": "--with-factors"}
        if config.include_ml:
            from portfolio_research_desk.ml_config import MLConfig
            from portfolio_research_desk.ml_reporting import save_ml_report
            from portfolio_research_desk.ml_workflow import run_ml_experiment

            ml = run_ml_experiment(MLConfig())
            report = save_ml_report(ml, directory / "ml", "validation")
            components["ml"] = {
                "status": "complete",
                "file": report.relative_to(directory).as_posix() + "/report.html",
                "scope": (
                    "synthetic purged OOS software validation; its longer fixture "
                    "is separate from the 6-session baseline"
                ),
            }
            components["ml_to_paper"] = _ml_preview(ml, directory, config.initial_cash_cad)
        else:
            components["ml"] = {"status": "not_requested", "enable": "--with-ml"}
        _write_index(directory, components, summary)
        write_json(
            directory / "workflow.json",
            {
                "schema_version": 6,
                "phase": 6,
                "status": "complete",
                "data_kind": "synthetic",
                "credible_real_market_oos": False,
                "components": components,
                "files": bundle_hashes(directory),
            },
        )
        return {
            "phase": 6,
            "status": "complete",
            "data_kind": "synthetic",
            "credible_real_market_oos": False,
            "report_directory": str(directory),
            "index": str(directory / "index.html"),
            "components": components,
        }
    except OSError as exc:
        raise ReportError(
            "Workflow output is incomplete; inspect the reserved directory "
            "before retrying with a new ID."
        ) from exc


def _write_index(directory, components, summary):
    rows = []
    for name, part in components.items():
        label = html.escape(name.replace("_", " ").title())
        status = html.escape(part["status"])
        link = (
            f'<a href="{html.escape(part["file"], quote=True)}">Open report</a>'
            if "file" in part
            else html.escape(part.get("enable", ""))
        )
        rows.append(
            f"<tr><td>{label}</td><td>{status}</td><td>{link}</td>"
            f"<td>{html.escape(part.get('scope', ''))}</td></tr>"
        )
    doc = (
        files("portfolio_research_desk")
        .joinpath("resources/workflow_index.html")
        .read_text("utf-8")
    )
    valuation = summary["last_recorded_valuation"]
    cash = ", ".join(f"{currency} {amount:.2f}" for currency, amount in summary["cash"])
    holdings = "".join(
        f"<tr><td>{html.escape(p.asset.symbol)}</td><td>{p.quantity}</td>"
        f"<td>{html.escape(p.asset.currency)}</td></tr>"
        for p in summary["positions"]
    )
    account = (
        f"<p><strong>NAV: CAD {valuation.nav_cad:.2f}</strong> at "
        f"{html.escape(valuation.as_of.isoformat())}</p>"
        f"<p>Cash: {html.escape(cash)}. Commission: CAD {summary['commission_cad']:.2f}. "
        f"FX conversion costs: CAD {summary['fx_cost_cad']:.2f}.</p>"
        "<table><thead><tr><th>Holding</th><th>Shares</th><th>Currency</th></tr></thead>"
        f"<tbody>{holdings}</tbody></table>"
        '<p><a href="account-summary.json">Account details (JSON)</a> · '
        '<a href="review-plan.json">Proposed weights and orders</a> · '
        '<a href="paper/account/trades.csv">Simulated trades (CSV)</a></p>'
    )
    doc = doc.replace("{{components}}", "".join(rows)).replace("{{account}}", account)
    (directory / "index.html").write_text(doc, encoding="utf-8")
