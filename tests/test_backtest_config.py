from dataclasses import replace
from decimal import Decimal as D
from importlib.resources import files
from pathlib import Path

import pytest

from portfolio_research_desk.backtest_config import BacktestConfig, load_backtest_config
from portfolio_research_desk.errors import ConfigError

DEFAULT = files("portfolio_research_desk").joinpath("resources/backtest.toml").read_text("utf-8")


def test_packaged_config_matches_editable_example():
    assert load_backtest_config() == load_backtest_config(Path("configs/example_backtest.toml"))
    assert load_backtest_config() == BacktestConfig()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("initial_cash", D("0")),
        ("initial_cash", D("NaN")),
        ("initial_cash", D("1.001")),
        ("initial_cash", 100),
        ("top_k", True),
        ("lookback_sessions", 0),
        ("top_k", 4),
        ("max_position_weight", D("1.1")),
        ("cash_buffer", D("-0.1")),
        ("commission_bps", D("-1")),
        ("slippage_bps", D("10000")),
        ("fixed_fee", D("0.001")),
        ("symbols", ()),
        ("symbols", ("SYN_A", "SYN_A")),
        ("log_level", "QUIET"),
    ],
)
def test_programmatic_config_rejects_invalid_settings(field, value):
    with pytest.raises(ConfigError):
        replace(BacktestConfig(), **{field: value})


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('base_currency = "USD"', 'base_currency = "CAD"'),
        ('data_source = "synthetic"', 'data_source = "yfinance"'),
        ('membership_type = "user_static"', 'membership_type = "point_in_time"'),
        ('source = "custom"', 'source = "index"'),
        ('name = "momentum_top_k"', 'name = "random_forest"'),
        ('fill_policy = "next_session_open"', 'fill_policy = "same_close"'),
        ("fractional_shares = false", "fractional_shares = 0"),
        ('initial_cash = "1000.00"', "initial_cash = true"),
        ('cash_buffer = "0.10"', 'cash_buffer = "NaN"'),
        ("top_k = 2", "top_k = true"),
        ("schema_version = 1", "schema_version = true"),
        ('slippage_bps = "10"', 'slippage_bps = "invalid"'),
    ],
)
def test_file_config_rejects_unsupported_or_unsafe_values(tmp_path, before, after):
    path = tmp_path / "config.toml"
    path.write_text(DEFAULT.replace(before, after), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_backtest_config(path)


def test_unknown_tables_and_missing_fields_are_rejected(tmp_path):
    for content in (
        DEFAULT + "\n[models]\nxgboost = true\n",
        DEFAULT.replace('market = "US"', ""),
        "",
    ):
        path = tmp_path / "bad.toml"
        path.write_text(content, encoding="utf-8")
        with pytest.raises(ConfigError):
            load_backtest_config(path)


def test_symbols_are_normalized_and_deduplicated(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        DEFAULT.replace('["SYN_A", "SYN_B", "SYN_C"]', '[" syn_a ", "SYN_A", "SYN_B"]'),
        encoding="utf-8",
    )
    assert load_backtest_config(path).symbols == ("SYN_A", "SYN_B")


def test_missing_and_invalid_encoding_are_reported(tmp_path):
    with pytest.raises(ConfigError):
        load_backtest_config(tmp_path / "missing")
    path = tmp_path / "bad.toml"
    path.write_bytes(b"\xff")
    with pytest.raises(ConfigError):
        load_backtest_config(path)
