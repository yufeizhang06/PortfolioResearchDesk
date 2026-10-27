import json
import logging
import re
import socket
import subprocess
import sys

import pytest
from pytest_socket import SocketBlockedError

from portfolio_research_desk.cli import main
from portfolio_research_desk.errors import SampleError


def test_help_and_version_from_installed_module():
    result = subprocess.run(
        [sys.executable, "-I", "-m", "portfolio_research_desk", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Phase 0" in result.stdout
    assert "demo" in result.stdout
    result = subprocess.run(
        [sys.executable, "-I", "-m", "portfolio_research_desk", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert re.fullmatch(r"prd \d+\.\d+\.\d+", result.stdout.strip())


def test_demo_json_and_log(capsys, caplog):
    caplog.set_level(logging.INFO)
    assert main(["demo"]) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert payload["phase"] == 0
    assert payload["sample"]["rows"] == 9
    assert "synthetic sample" in caplog.text


def test_validate_config(capsys):
    assert main(["config", "validate", "--config", "configs/example_offline.toml"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["config"]["mode"] == "offline_sample"
    assert "sample" not in payload


@pytest.mark.parametrize("args", [[], ["backtest"], ["config"], ["demo", "--unknown"]])
def test_invalid_command_is_usage_error(args, capsys):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "error:" in output.err
    assert "Traceback" not in output.err


def test_missing_config_is_actionable(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["demo", "--config", str(tmp_path / "missing.toml")])
    assert exc.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "Cannot read" in output.err


def test_sample_error_has_no_success_output(monkeypatch, capsys):
    def fail():
        raise SampleError("Invalid sample.")

    monkeypatch.setattr("portfolio_research_desk.cli.summarize_sample", fail)
    with pytest.raises(SystemExit) as exc:
        main(["demo"])
    assert exc.value.code == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "Invalid sample" in output.err


def test_test_process_cannot_open_network_socket():
    with pytest.warns(UserWarning, match="socket.socket"), pytest.raises(SocketBlockedError):
        socket.socket()
