"""Cross-component delivery tests, independent NAV checks and report integrity."""

import json
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

from portfolio_research_desk.delivery_reports import verify_workflow_report
from portfolio_research_desk.errors import ConfigError, DataError, ReportError
from portfolio_research_desk.paper_store import PaperAccount
from portfolio_research_desk.product_workflow import run_workflow
from portfolio_research_desk.workflow_config import WorkflowConfig, load_workflow_config
from portfolio_research_desk.workflow_fixtures import delivery_inputs


def test_base_workflow_shared_universe_signals_paper_and_independent_nav(tmp_path):
    result = run_workflow(WorkflowConfig(output_dir=tmp_path), "base")
    directory = Path(result["report_directory"])
    checked = verify_workflow_report(directory)
    assert checked["status"] == "verified" and checked["file_count"] >= 20
    assert result["components"]["factors"]["status"] == "not_requested"
    assert result["components"]["ml"]["status"] == "not_requested"
    research = json.loads((directory / "research.json").read_text("utf-8"))
    assert research["data_kind"] == "synthetic" and research["credible_real_market_oos"] is False
    account = PaperAccount(directory / "account.sqlite3").load()
    assert account.event_count == 5 and len(account.valuations) == 2
    plan = account.plans["workflow"].plan
    assert plan.signals.universe.assets == delivery_inputs()["bundle"].universe.assets
    assert plan.signals.signals == delivery_inputs()["bundle"].signals
    assert all(
        s.available_at <= plan.decision_at < plan.session.open_at for s in plan.signals.signals
    )
    prices = {q.asset: Fraction(q.price) for q in delivery_inputs()["closing"].quotes}
    cash = account.state.balances()
    independent = Fraction(cash["CAD"]) + Fraction(cash["USD"]) * Fraction(13, 10)
    independent += sum(
        (p.quantity * prices[p.asset] * Fraction(13, 10) for p in account.state.positions),
        Fraction(0),
    )
    assert Fraction(account.valuations[-1].nav_cad) == independent
    assert not account.valuations[-1].violations
    assert (
        json.loads((directory / "review-plan.json").read_text("utf-8"))["status"]
        == "PENDING_REVIEW"
    )
    assert account.plans["workflow"].status == "SIMULATED"
    html = (directory / "index.html").read_text("utf-8")
    assert "SYNTHETIC SOFTWARE VERIFICATION" in html and "{{" not in html
    assert "https://" not in html  # Index has only local links, no remote assets.


def test_full_workflow_factor_ml_and_pending_preview(tmp_path):
    result = run_workflow(
        WorkflowConfig(include_factors=True, include_ml=True, output_dir=tmp_path), "full"
    )
    directory = Path(result["report_directory"])
    assert verify_workflow_report(directory)["status"] == "verified"
    assert result["components"]["factors"]["status"] == "complete"
    assert result["components"]["ml"]["status"] == "complete"
    preview = json.loads((directory / "ml-paper-preview.json").read_text("utf-8"))
    assert preview["status"] == "PENDING_REVIEW" and preview["fills"] == []
    assert preview["selected_model"] == result["components"]["ml_to_paper"]["selected_model"]
    assert preview["credible_real_market_oos"] is False
    assert preview["plan"]["signals"]["source"].startswith("ml:")
    assert "independent known-answer factor fixture" in (directory / "index.html").read_text(
        "utf-8"
    )


def test_repeated_configs_reproduce_numeric_results_and_never_overwrite(tmp_path):
    config = WorkflowConfig(output_dir=tmp_path)
    a = run_workflow(config, "one")
    b = run_workflow(config, "two")
    assert a["components"]["paper_cad"] == b["components"]["paper_cad"]
    with pytest.raises(ReportError, match="never overwritten"):
        run_workflow(config, "one")
    assert verify_workflow_report(tmp_path / "one")["status"] == "verified"


@pytest.mark.parametrize("case", ["modified", "missing", "extra", "nested_manifest"])
def test_report_mutation_is_detected(tmp_path, case):
    run_workflow(WorkflowConfig(output_dir=tmp_path), "run")
    path = tmp_path / "run" / "research.json"
    if case == "modified":
        path.write_text("{}")
    elif case == "missing":
        path.unlink()
    elif case == "extra":
        (tmp_path / "run" / "unexpected.txt").write_text("untracked")
    else:
        (tmp_path / "run" / "nested").mkdir()
        (tmp_path / "run" / "nested" / "workflow.json").write_text("{}")
    with pytest.raises(ReportError, match="changed"):
        verify_workflow_report(tmp_path / "run")


@pytest.mark.parametrize(
    "name", ["../outside", "/etc/passwd", "C:/private", "sub\\private", "./local", ""]
)
def test_manifest_paths_cannot_escape(tmp_path, name):
    directory = tmp_path / "run"
    directory.mkdir()
    marker = dict(
        schema_version=6,
        phase=6,
        status="complete",
        data_kind="synthetic",
        credible_real_market_oos=False,
        components={},
        files={name: "0" * 64},
    )
    (directory / "workflow.json").write_text(json.dumps(marker))
    with pytest.raises(ReportError):
        verify_workflow_report(directory)


def test_missing_dependency_preflight_leaves_no_output(tmp_path, monkeypatch):
    import portfolio_research_desk.product_workflow as workflow

    def missing(_):
        raise DataError("Install factors extra")

    monkeypatch.setattr(workflow, "require_workflow_extras", missing)
    with pytest.raises(DataError):
        run_workflow(WorkflowConfig(output_dir=tmp_path / "output"), "run")
    assert not (tmp_path / "output").exists()


def test_failed_component_has_no_workflow_completion_marker(tmp_path, monkeypatch):
    import portfolio_research_desk.product_workflow as workflow

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(workflow, "write_paper_report", fail)
    with pytest.raises(ReportError):
        run_workflow(WorkflowConfig(output_dir=tmp_path), "broken")
    assert not (tmp_path / "broken" / "workflow.json").exists()
    with pytest.raises(ReportError):
        verify_workflow_report(tmp_path / "broken")


@pytest.mark.parametrize(
    "field,value",
    [
        ("initial_cash_cad", Decimal("NaN")),
        ("top_k", True),
        ("top_k", 0),
        ("top_k", 4),
        ("include_factors", 1),
        ("include_ml", "true"),
        ("output_dir", "outputs"),
    ],
)
def test_invalid_workflow_config(field, value):
    with pytest.raises((ConfigError, DataError)):
        replace(WorkflowConfig(), **{field: value})


def test_configuration_paths_are_relative_to_file(tmp_path):
    path = tmp_path / "profile.toml"
    content = (
        Path("configs/example_workflow.toml")
        .read_text("utf-8")
        .replace('"../outputs/workflows"', '"runs"')
    )
    path.write_text(content)
    assert load_workflow_config(path).output_dir == tmp_path / "runs"
    path.write_text(content.replace('"synthetic_demo"', '"live"'))
    with pytest.raises(ConfigError):
        load_workflow_config(path)
