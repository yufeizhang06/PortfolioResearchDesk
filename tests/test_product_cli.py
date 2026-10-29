"""CLI usability and native compatibility without network or hidden approval."""

import json
from datetime import timedelta
from decimal import Decimal

import pytest

from portfolio_research_desk.cli import main
from portfolio_research_desk.diagnostics import inspect_environment
from portfolio_research_desk.paper_store import PaperAccount
from portfolio_research_desk.workflow_config import load_workflow_config
from portfolio_research_desk.workflow_fixtures import delivery_inputs


def invoke(capsys, *args):
    code = main(list(map(str, args)))
    payload = json.loads(capsys.readouterr().out)
    return code, payload


def test_doctor_is_offline_and_explains_optional_extras(capsys):
    code, payload = invoke(capsys, "doctor", "--require", "factors", "--require", "ml")
    assert code == 0 and payload["status"] == "ready"
    assert payload["network_accessed"] is False
    assert "uv sync --locked --extra ml" == payload["extras"]["ml"]["install_command"]


def test_missing_extra_is_diagnosed_without_installing(monkeypatch, capsys):
    import portfolio_research_desk.diagnostics as diagnostics

    original = diagnostics.metadata.version

    def version(name):
        if name == "xgboost":
            raise diagnostics.metadata.PackageNotFoundError(name)
        return original(name)

    monkeypatch.setattr(diagnostics.metadata, "version", version)
    code, payload = invoke(capsys, "doctor", "--require", "ml")
    assert code == 2 and payload["missing_required_extras"] == ["ml"]
    assert inspect_environment()["status"] == "ready"  # Base features remain usable.


def test_workspace_templates_paths_and_exclusive_creation(tmp_path, capsys):
    root = tmp_path / "desk with spaces"
    code, payload = invoke(capsys, "workspace", "init", "--directory", root)
    assert code == 0 and payload["data_kind"] == "synthetic"
    assert load_workflow_config(root / "workflow.toml").output_dir == root / "runs"
    for purpose in ("decision", "opening", "closing"):
        assert (
            invoke(capsys, "paper", "validate-snapshot", "--snapshot", root / (purpose + ".json"))[
                0
            ]
            == 0
        )
    ignores = (root / ".gitignore").read_text("utf-8")
    assert all(value in ignores for value in ("/runs/", "/data/", "/private/", "*.sqlite*", ".env"))
    with pytest.raises(SystemExit) as exc:
        main(["workspace", "init", "--directory", str(root)])
    assert exc.value.code == 2
    assert load_workflow_config(root / "workflow.toml").initial_cash_cad == 3000


def test_readable_manual_paper_roundtrip_and_stale_nav(tmp_path, capsys):
    root = tmp_path / "desk"
    invoke(capsys, "workspace", "init", "--directory", root)
    x = delivery_inputs()
    db = root / "accounts" / "paper.sqlite3"
    invoke(
        capsys, "paper", "init", "--db", db, "--at", x["dataset"].sessions[0].open_at.isoformat()
    )
    _, proposed = invoke(
        capsys,
        "paper",
        "plan",
        "--db",
        db,
        "--snapshot",
        root / "decision.json",
        "--plan-id",
        "manual",
    )
    assert proposed["plan"]["status"] == "PENDING_REVIEW"
    assert proposed["plan"]["orders"]
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "paper",
                "simulate",
                "--db",
                str(db),
                "--snapshot",
                str(root / "opening.json"),
                "--plan-id",
                "manual",
            ]
        )
    assert exc.value.code == 2
    capsys.readouterr()
    invoke(
        capsys,
        "paper",
        "review",
        "--db",
        db,
        "--plan-id",
        "manual",
        "--plan-hash",
        proposed["plan"]["plan_hash"],
        "--approve",
        "--at",
        (x["decision_at"] + timedelta(seconds=30)).isoformat(),
    )
    command = (
        "paper",
        "simulate",
        "--db",
        db,
        "--snapshot",
        root / "opening.json",
        "--plan-id",
        "manual",
    )
    code, filled = invoke(capsys, *command)
    assert code == 0 and filled["plan"]["status"] == "SIMULATED"
    assert invoke(capsys, *command)[1] == filled
    _, valued = invoke(
        capsys,
        "paper",
        "value",
        "--db",
        db,
        "--snapshot",
        root / "closing.json",
        "--event-id",
        "close",
    )
    assert valued["valuation_stale"] is False
    assert valued["last_recorded_valuation"]["as_of"] == x["valuation_at"].isoformat()
    assert invoke(capsys, "paper", "summary", "--db", db)[1] == valued
    at = x["valuation_at"].isoformat()
    flow = (
        "paper",
        "cash-flow",
        "--db",
        db,
        "--event-id",
        "deposit",
        "--currency",
        "CAD",
        "--amount",
        "10",
        "--at",
        at,
    )
    _, after = invoke(capsys, *flow)
    assert after["valuation_stale"] is True
    assert after["last_recorded_valuation"] == valued["last_recorded_valuation"]
    assert invoke(capsys, *flow)[1] == after
    _, latest = invoke(
        capsys,
        "paper",
        "value",
        "--db",
        db,
        "--snapshot",
        root / "closing.json",
        "--event-id",
        "after-deposit",
    )
    assert latest["valuation_stale"] is False
    assert (
        Decimal(latest["last_recorded_valuation"]["nav_cad"])
        - Decimal(valued["last_recorded_valuation"]["nav_cad"])
        == 10
    )
    fx = root / "fx.csv"
    fx.write_text(
        "observed_at,available_at,cad_per_usd,source,synthetic\n"
        + f"{at},{at},1.30,synthetic_cli,true\n",
        encoding="utf-8",
    )
    _, converted = invoke(
        capsys,
        "paper",
        "convert",
        "--db",
        db,
        "--event-id",
        "usd",
        "--source",
        "CAD",
        "--usd-amount",
        "10",
        "--fx-csv",
        fx,
        "--at",
        at,
    )
    assert dict(converted["cash"])["USD"] == "10.00"
    assert converted["valuation_stale"] is True
    _, marked = invoke(
        capsys,
        "paper",
        "value",
        "--db",
        db,
        "--snapshot",
        root / "closing.json",
        "--event-id",
        "after-fx",
    )
    assert Decimal(latest["last_recorded_valuation"]["nav_cad"]) - Decimal(
        marked["last_recorded_valuation"]["nav_cad"]
    ) == Decimal(".03")
    assert PaperAccount(db).load().valuations[-1].nav_cad == Decimal(
        marked["last_recorded_valuation"]["nav_cad"]
    )


def test_snapshot_clock_conflict_leaves_account_untouched(tmp_path, capsys):
    root = tmp_path / "desk"
    invoke(capsys, "workspace", "init", "--directory", root)
    x = delivery_inputs()
    db = root / "paper.sqlite3"
    invoke(
        capsys, "paper", "init", "--db", db, "--at", x["dataset"].sessions[0].open_at.isoformat()
    )
    before = PaperAccount(db).load()
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "paper",
                "simulate",
                "--db",
                str(db),
                "--plan-id",
                "unused",
                "--snapshot",
                str(root / "opening.json"),
                "--at",
                (x["execution_at"] + timedelta(seconds=1)).isoformat(),
            ]
        )
    assert exc.value.code == 2
    assert PaperAccount(db).load() == before


def test_legacy_native_simulation_requires_its_explicit_time(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "paper",
                "simulate",
                "--db",
                str(tmp_path / "missing.sqlite3"),
                "--input",
                "not-needed.json",
                "--plan-id",
                "p",
            ]
        )
    assert exc.value.code == 2 and "requires --at" in capsys.readouterr().err
    assert not (tmp_path / "missing.sqlite3").exists()


def test_config_and_workflow_cli_entries(tmp_path, capsys):
    code, payload = invoke(capsys, "config", "validate", "--kind", "workflow")
    assert code == 0 and payload["config"]["mode"] == "synthetic_demo"
    code, result = invoke(capsys, "workflow", "run", "--output-dir", tmp_path, "--run-id", "cli")
    assert code == 0
    code, checked = invoke(capsys, "workflow", "check", "--directory", result["report_directory"])
    assert code == 0 and checked["status"] == "verified"
