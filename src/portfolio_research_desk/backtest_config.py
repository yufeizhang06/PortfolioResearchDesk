"""Strict, versioned Phase 1 settings; Phase 0 configuration remains compatible."""

import tomllib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from importlib.resources import files
from pathlib import Path
from typing import Any

from portfolio_research_desk.domain import CENT, ONE, ZERO
from portfolio_research_desk.errors import ConfigError


@dataclass(frozen=True)
class BacktestConfig:
    symbols: tuple[str, ...] = ("SYN_A", "SYN_B", "SYN_C")
    initial_cash: Decimal = Decimal("1000.00")
    lookback_sessions: int = 1
    top_k: int = 2
    max_position_weight: Decimal = Decimal("0.60")
    cash_buffer: Decimal = Decimal("0.10")
    commission_bps: Decimal = Decimal("5")
    fixed_fee: Decimal = Decimal("0.10")
    slippage_bps: Decimal = Decimal("10")
    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.symbols, tuple)
            or not self.symbols
            or any(not isinstance(s, str) or not s.startswith("SYN_") for s in self.symbols)
            or len(set(self.symbols)) != len(self.symbols)
        ):
            raise ConfigError("symbols must be nonempty unique SYN_ synthetic asset identifiers.")
        for field in ("lookback_sessions", "top_k"):
            if type(getattr(self, field)) is not int or getattr(self, field) < 1:
                raise ConfigError(f"{field} must be a positive integer.")
        if self.top_k > len(self.symbols):
            raise ConfigError("top_k cannot exceed the custom universe size.")
        for field in (
            "initial_cash",
            "max_position_weight",
            "cash_buffer",
            "commission_bps",
            "fixed_fee",
            "slippage_bps",
        ):
            value = getattr(self, field)
            if (
                not isinstance(value, Decimal)
                or not value.is_finite()
                or not ZERO <= value <= Decimal("1e12")
            ):
                raise ConfigError(f"{field} must be a finite nonnegative Decimal at most 1e12.")
        if self.initial_cash < CENT or self.initial_cash != self.initial_cash.quantize(CENT):
            raise ConfigError("initial_cash must be positive whole USD cents.")
        if not ZERO < self.max_position_weight <= ONE or not ZERO <= self.cash_buffer <= ONE:
            raise ConfigError("Position weight must be in (0,1]; cash_buffer in [0,1].")
        if self.commission_bps > Decimal("10000") or self.slippage_bps >= Decimal("10000"):
            raise ConfigError("commission_bps must be <=10000 and slippage_bps <10000.")
        if self.fixed_fee != self.fixed_fee.quantize(CENT):
            raise ConfigError("fixed_fee must be denominated in whole cents.")
        if type(self.log_level) is not str or self.log_level not in {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
        }:
            raise ConfigError("Invalid log_level.")

    def snapshot(self) -> dict[str, Any]:
        """All effective settings, including fixed Phase 1 assumptions."""
        return {
            "schema_version": 1,
            "mode": "backtest",
            "market": "US",
            "data_source": "synthetic",
            "log_level": self.log_level,
            "universe": {
                "source": "custom",
                "membership_type": "user_static",
                "symbols": list(self.symbols),
            },
            "account": {"base_currency": "USD", "initial_cash": str(self.initial_cash)},
            "strategy": {
                "name": "momentum_top_k",
                "lookback_sessions": self.lookback_sessions,
                "top_k": self.top_k,
            },
            "portfolio": {
                "max_position_weight": str(self.max_position_weight),
                "cash_buffer": str(self.cash_buffer),
            },
            "execution": {
                "fill_policy": "next_session_open",
                "fractional_shares": False,
                "commission_bps": str(self.commission_bps),
                "fixed_fee": str(self.fixed_fee),
                "slippage_bps": str(self.slippage_bps),
            },
        }


def _table(value: Any, keys: set[str], label: str, optional: set[str] | None = None) -> dict:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a TOML table.")
    optional = optional or set()
    if value.keys() - keys - optional or keys - value.keys():
        raise ConfigError(f"{label} has unknown or missing fields.")
    return value


def _decimal(value: Any, name: str) -> Decimal:
    if type(value) not in (int, str, Decimal):
        raise ConfigError(f"{name} requires a decimal string or number; booleans are not numbers.")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ConfigError(f"Invalid decimal for {name}.") from exc


def load_backtest_config(path: Path | None = None) -> BacktestConfig:
    try:
        raw = (
            path.read_bytes()
            if path
            else files("portfolio_research_desk").joinpath("resources/backtest.toml").read_bytes()
        )
        values = tomllib.loads(raw.decode("utf-8"), parse_float=Decimal)
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError("Cannot read UTF-8 backtest TOML configuration.") from exc
    root = _table(
        values,
        {
            "schema_version",
            "mode",
            "market",
            "data_source",
            "universe",
            "account",
            "strategy",
            "portfolio",
            "execution",
        },
        "config",
        {"log_level"},
    )
    if type(root["schema_version"]) is not int or root["schema_version"] != 1:
        raise ConfigError("schema_version must be integer 1.")
    if (root["mode"], root["market"], root["data_source"]) != ("backtest", "US", "synthetic"):
        raise ConfigError("Phase 1 requires backtest / US / synthetic.")
    universe = _table(root["universe"], {"source", "membership_type", "symbols"}, "universe")
    if (universe["source"], universe["membership_type"]) != ("custom", "user_static"):
        raise ConfigError(
            "Phase 1 accepts custom user_static universes, never PIT/current index claims."
        )
    symbols = universe["symbols"]
    if not isinstance(symbols, list) or not symbols or any(type(s) is not str for s in symbols):
        raise ConfigError("universe.symbols must be a nonempty string array.")
    symbols = tuple(dict.fromkeys(s.strip().upper() for s in symbols))
    account = _table(root["account"], {"base_currency", "initial_cash"}, "account")
    if account["base_currency"] != "USD":
        raise ConfigError("Phase 1 is USD-only; CAD/FX is not implemented.")
    strategy = _table(root["strategy"], {"name", "lookback_sessions", "top_k"}, "strategy")
    if strategy["name"] != "momentum_top_k":
        raise ConfigError("Phase 1 implements momentum_top_k only.")
    portfolio = _table(root["portfolio"], {"max_position_weight", "cash_buffer"}, "portfolio")
    execution = _table(
        root["execution"],
        {"fill_policy", "fractional_shares", "commission_bps", "fixed_fee", "slippage_bps"},
        "execution",
    )
    if (
        execution["fill_policy"] != "next_session_open"
        or execution["fractional_shares"] is not False
    ):
        raise ConfigError("Phase 1 requires next_session_open and fractional_shares=false.")
    return BacktestConfig(
        symbols=symbols,
        initial_cash=_decimal(account["initial_cash"], "initial_cash"),
        lookback_sessions=strategy["lookback_sessions"],
        top_k=strategy["top_k"],
        max_position_weight=_decimal(portfolio["max_position_weight"], "max_position_weight"),
        cash_buffer=_decimal(portfolio["cash_buffer"], "cash_buffer"),
        commission_bps=_decimal(execution["commission_bps"], "commission_bps"),
        fixed_fee=_decimal(execution["fixed_fee"], "fixed_fee"),
        slippage_bps=_decimal(execution["slippage_bps"], "slippage_bps"),
        log_level=root.get("log_level", "INFO"),
    )
