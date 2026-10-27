from importlib.resources import files

import pytest

from portfolio_research_desk.errors import ConfigError
from portfolio_research_desk.research_config import load_research_config

DEFAULT = files("portfolio_research_desk").joinpath("resources/research.toml").read_text("utf-8")


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('mode = "custom"', 'mode = "unknown"'),
        ('expected_kind = "synthetic"', 'expected_kind = "real"'),
        ('adapter = "csv"', 'adapter = "unknown"'),
        ("schema_version = 2", "schema_version = true"),
        ("offline = true", "offline = 1"),
        ("min_history = 3", "min_history = true"),
        ('min_momentum = "0"', 'min_momentum = "NaN"'),
        ('max_volatility = "10"', 'max_volatility = "-1"'),
        ("enabled = true", "enabled = false"),
        ('end = "2024-01-10"', 'end = "2024-01-01"'),
        ("momentum_sessions = 1", "momentum_sessions = 0"),
    ],
)
def test_invalid_or_unsupported_config_fails_closed(tmp_path, before, after):
    path = tmp_path / "research.toml"
    path.write_text(DEFAULT.replace(before, after), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_research_config(path)


def test_paths_are_relative_to_config_and_unknown_tables_rejected(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        DEFAULT + '\n[storage]\ncache_dir = "cache"\noutput_dir = "results"\n', encoding="utf-8"
    )
    cfg = load_research_config(path)
    assert cfg.cache_dir == tmp_path / "cache" and cfg.output_dir == tmp_path / "results"
    path.write_text(DEFAULT + "\n[models]\nxgboost = true\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_research_config(path)
