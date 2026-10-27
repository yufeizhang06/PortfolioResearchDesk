from dataclasses import FrozenInstanceError
from importlib.resources import files
from pathlib import Path

import pytest

from portfolio_research_desk.config import load_config
from portfolio_research_desk.errors import ConfigError

DEFAULT = files("portfolio_research_desk").joinpath("resources/default.toml").read_text("utf-8")


def write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "test.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_default_matches_editable_example():
    config = load_config()
    assert config == load_config(Path("configs/example_offline.toml"))
    assert config.snapshot() == {
        "schema_version": 1,
        "mode": "offline_sample",
        "data_source": "synthetic",
        "currency": "USD",
        "log_level": "INFO",
    }
    with pytest.raises(FrozenInstanceError):
        config.currency = "CAD"


def test_log_level_can_be_omitted(tmp_path):
    content = DEFAULT.replace('log_level = "INFO"', "")
    assert load_config(write_config(tmp_path, content)).log_level == "INFO"


@pytest.mark.parametrize(
    ("before", "after", "error"),
    [
        ('mode = "offline_sample"', 'mode = "backtest"', "Phase 0 supports mode"),
        ('mode = "offline_sample"', 'mode = "paper"', "Phase 0 supports mode"),
        ('data_source = "synthetic"', 'data_source = "yfinance"', "data_source"),
        ('currency = "USD"', 'currency = "CAD"', "USD-only"),
        ("schema_version = 1", "schema_version = true", "integer 1"),
        ("schema_version = 1", 'schema_version = "1"', "integer 1"),
        ("schema_version = 1", "schema_version = 2", "integer 1"),
        ('log_level = "INFO"', 'log_level = "quiet"', "log_level"),
        ('log_level = "INFO"', "log_level = 1", "must be a string"),
        ('mode = "offline_sample"', "mode = false", "must be a string"),
    ],
)
def test_reject_unsupported_values(tmp_path, before, after, error):
    with pytest.raises(ConfigError, match=error):
        load_config(write_config(tmp_path, DEFAULT.replace(before, after)))


@pytest.mark.parametrize(
    ("content", "error"),
    [
        (DEFAULT + "\nrandom_seed = 42\n", "Unknown config fields"),
        (DEFAULT.replace('currency = "USD"', ""), "Missing config fields"),
        ("", "Missing config fields"),
        ("[broken", "UTF-8 TOML"),
        (DEFAULT + '\nmode = "paper"\n', "UTF-8 TOML"),
    ],
)
def test_reject_invalid_documents(tmp_path, content, error):
    with pytest.raises(ConfigError, match=error):
        load_config(write_config(tmp_path, content))


def test_missing_and_non_utf8_files(tmp_path):
    with pytest.raises(ConfigError, match="Cannot read"):
        load_config(tmp_path / "missing.toml")
    path = tmp_path / "invalid.toml"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(ConfigError, match="Cannot read"):
        load_config(path)


def test_default_is_independent_of_cwd_and_environment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PRD_MODE", "backtest")
    (tmp_path / "config.toml").write_text('mode = "paper"', encoding="utf-8")
    assert load_config().mode == "offline_sample"
