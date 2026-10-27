import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from portfolio_research_desk.backtest import run_backtest
from portfolio_research_desk.backtest_config import BacktestConfig
from portfolio_research_desk.cli import main
from portfolio_research_desk.errors import ReportError
from portfolio_research_desk.reporting import write_report


def test_run_bundle_contains_reconcilable_snapshots_and_ledger(tmp_path):
    result = run_backtest(BacktestConfig())
    directory = write_report(result, tmp_path, "known-run")
    marker = json.loads((directory / "run.json").read_text("utf-8"))
    payload = json.loads((directory / "result.json").read_text("utf-8"))
    assert marker["status"] == "complete" and marker["phase"] == 1
    assert marker["config_hash"] and marker["data_snapshot_hash"] == result.data_hash
    assert marker["source_code_hash"] and marker["python_version"]
    assert payload["config"]["account"]["base_currency"] == "USD"
    for filename in marker["report_paths"]:
        assert (directory / filename).is_file()
    with (directory / "fills.csv").open(encoding="utf-8", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == len(result.fills)
    html = (directory / "report.html").read_text("utf-8")
    assert (
        "SYNTHETIC" in html and "user_static" in html and "not historical market evidence" in html
    )
    assert not any(token in html for token in ("https://", "<script", "cdn."))


def test_existing_run_is_never_overwritten(tmp_path):
    result = run_backtest(BacktestConfig())
    directory = write_report(result, tmp_path, "immutable")
    original = {p.name: p.read_bytes() for p in directory.iterdir()}
    with pytest.raises(ReportError, match="never overwritten"):
        write_report(result, tmp_path, "immutable")
    assert original == {p.name: p.read_bytes() for p in directory.iterdir()}


@pytest.mark.parametrize("run_id", ["../escape", ".", "CON", "a/b", "", "a" * 81])
def test_unsafe_run_id_is_rejected(tmp_path, run_id):
    with pytest.raises(ReportError):
        write_report(run_backtest(BacktestConfig()), tmp_path, run_id)
    assert not list(tmp_path.iterdir())


def test_default_run_ids_are_unique(tmp_path):
    result = run_backtest(BacktestConfig())
    assert write_report(result, tmp_path) != write_report(result, tmp_path)


def test_cli_offline_backtest_from_another_working_directory(tmp_path):
    process = subprocess.run(
        [
            sys.executable,
            "-I",
            "-m",
            "portfolio_research_desk",
            "backtest",
            "run",
            "--output-dir",
            str(tmp_path / "runs"),
            "--run-id",
            "cli-e2e",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(process.stdout)
    assert payload["phase"] == 1
    assert payload["metrics"]["fill_count"] > 0
    assert Path(payload["report_directory"]).joinpath("run.json").is_file()
    assert "synthetic USD backtest" in process.stderr


def test_backtest_config_cli_and_duplicate_run_error(tmp_path, capsys):
    assert main(["config", "validate", "--kind", "backtest"]) == 0
    assert json.loads(capsys.readouterr().out)["phase"] == 1
    args = ["backtest", "run", "--output-dir", str(tmp_path), "--run-id", "fixed"]
    assert main(args) == 0
    capsys.readouterr()
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert not captured.out and "never overwritten" in captured.err


def test_io_failure_leaves_no_completion_marker(tmp_path, monkeypatch):
    def fail(*_args):
        raise OSError("disk full")

    monkeypatch.setattr("portfolio_research_desk.reporting._write_csv", fail)
    with pytest.raises(ReportError, match="Incomplete"):
        write_report(run_backtest(BacktestConfig()), tmp_path, "failed")
    assert not (tmp_path / "failed/run.json").exists()
