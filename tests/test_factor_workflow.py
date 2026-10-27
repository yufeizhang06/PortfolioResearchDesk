import hashlib
import json
from dataclasses import replace
from datetime import date
from importlib.resources import files
from pathlib import Path

import pytest

from portfolio_research_desk.cli import main
from portfolio_research_desk.errors import ConfigError, DataError, ReportError
from portfolio_research_desk.factor_config import load_factor_config
from portfolio_research_desk.factor_reporting import save_factor_report
from portfolio_research_desk.factor_workflow import run_factor_research
from portfolio_research_desk.research_config import load_research_config


def test_cli_factor_research_reports_and_immutable_completion(tmp_path, capsys):
    assert main(["research", "run", "--output-dir", str(tmp_path), "--run-id", "accepted"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["phase"] == 3 and payload["nobs"] == 96
    assert not payload["historical_signal_eligible"]
    directory = tmp_path / "accepted"
    marker = json.loads((directory / "run.json").read_text("utf-8"))
    assert marker["provenance"]["runtime_dependencies"]["statsmodels"]
    for name, digest in marker["artifact_hashes"].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest
    analysis = json.loads((directory / "analysis.json").read_text("utf-8"))
    assert analysis["fits"]["FF3"]["sample_hash"] == analysis["fits"]["FF4"]["sample_hash"]
    assert (directory / "exposure.svg").is_file() and (directory / "rolling.svg").is_file()
    assert "Ex-post descriptive" in (directory / "report.html").read_text("utf-8")
    before = (directory / "run.json").read_bytes()
    with pytest.raises(SystemExit) as error:
        main(["research", "run", "--output-dir", str(tmp_path), "--run-id", "accepted"])
    assert error.value.code == 2 and (directory / "run.json").read_bytes() == before


def test_cli_config_and_real_example_share_existing_acquisition_schema(capsys):
    assert main(["config", "validate", "--kind", "factors"]) == 0
    assert json.loads(capsys.readouterr().out)["config"]["schema_version"] == 3
    real = load_factor_config(Path("configs/example_factors_real.toml"))
    market = load_research_config(real.research_config)
    assert len(market.assets) == 1 and market.assets[0].symbol == "AAPL"


@pytest.mark.parametrize(
    "change",
    [
        {"frequency": "weekly"},
        {"return_basis": "total_return_magic"},
        {"min_obs": True},
        {"rolling_window": 3},
        {"min_obs": 5},
        {"confidence": 1},
        {"confidence": True},
        {"covariance": "HAC"},
        {"offline": "false"},
        {"expected_kind": "real"},
        {"start": date(2025, 1, 1)},
        {"factor_source": "french", "expected_kind": "real"},
    ],
)
def test_strict_config_conflicts_fail(change):
    with pytest.raises(ConfigError):
        replace(load_factor_config(), **change)


@pytest.mark.parametrize(
    "text",
    [
        "schema_version=true",
        "schema_version=2",
        'schema_version="3"',
        'schema_version=3\nunknown="field"',
        'schema_version=3\nstart="not-date"',
    ],
)
def test_malformed_factor_toml_is_user_error(tmp_path, text):
    path = tmp_path / "bad.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_factor_config(path)


def test_failed_statistics_still_have_explicit_diagnostic_bundle(tmp_path):
    config = replace(load_factor_config(), end=date(2024, 1, 10))
    result = run_factor_research(config)
    assert result.status == "failed" and result.comparison is None
    directory = save_factor_report(result, tmp_path, "short")
    marker = json.loads((directory / "run.json").read_text("utf-8"))
    assert marker["status"] == "failed" and any(
        "INSUFFICIENT_SAMPLE" in w for w in marker["warnings"]
    )
    assert (directory / "analysis.json").read_text("utf-8") == "null"


def test_io_failure_never_writes_completion_marker(tmp_path, monkeypatch):
    import portfolio_research_desk.factor_reporting as reporting

    result = run_factor_research(load_factor_config())

    def broken(*args, **kwargs):
        raise OSError("injected full disk")

    monkeypatch.setattr(reporting, "_csv", broken)
    with pytest.raises(ReportError, match="incomplete"):
        save_factor_report(result, tmp_path, "broken")
    assert not (tmp_path / "broken" / "run.json").exists()


def test_missing_factor_extra_is_input_error_before_acquisition(monkeypatch):
    import portfolio_research_desk.factor_analysis as analysis

    def absent():
        raise DataError("Install the locked factors extra.")

    monkeypatch.setattr(analysis, "_libraries", absent)
    with pytest.raises(DataError, match="factors extra"):
        run_factor_research(load_factor_config())


def test_local_factor_files_and_native_prices_share_workflow(tmp_path):
    resource = files("portfolio_research_desk").joinpath("resources")
    ff3, mom = tmp_path / "ff3.csv", tmp_path / "mom.csv"
    ff3.write_bytes(resource.joinpath("factors_ff3.csv").read_bytes())
    mom.write_bytes(resource.joinpath("factors_mom.csv").read_bytes())
    config = replace(
        load_factor_config(),
        factor_source="local",
        ff3_file=ff3,
        momentum_file=mom,
        price_file=Path(str(resource.joinpath("factor_prices.csv"))),
    )
    result = run_factor_research(config)
    assert result.status == "complete" and len(result.sample.rows) == 96
    assert result.comparison["fits"]["FF4"]["coefficients"]["Mom"]["estimate"] == pytest.approx(0.5)
    with pytest.raises(DataError, match="relabelled"):
        run_factor_research(replace(config, expected_kind="real"))


@pytest.mark.parametrize("run_id", ["../escape", "CON", "with space", "a" * 81])
def test_output_run_names_cannot_escape_root(tmp_path, run_id):
    result = run_factor_research(replace(load_factor_config(), end=date(2024, 1, 10)))
    with pytest.raises(ReportError, match="Unsafe"):
        save_factor_report(result, tmp_path, run_id)
