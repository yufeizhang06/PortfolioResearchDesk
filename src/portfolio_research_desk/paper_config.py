"""Strict Phase 5 configuration. No dependencies beyond the Python standard library."""

import tomllib
from dataclasses import dataclass, fields
from decimal import Decimal
from importlib.resources import files
from pathlib import Path

from portfolio_research_desk.backtest_config import _decimal, _table
from portfolio_research_desk.domain import jsonable
from portfolio_research_desk.errors import ConfigError, DataError
from portfolio_research_desk.paper_domain import Costs, money
from portfolio_research_desk.portfolio_risk import RiskLimits


@dataclass(frozen=True)
class PaperConfig:
    initial_cash: Decimal = Decimal("3000.00")
    top_k: int = 5
    limits: RiskLimits = RiskLimits()
    costs: Costs = Costs()

    def __post_init__(self):
        money(self.initial_cash, "initial cash", positive=True)
        if type(self.top_k) is not int or self.top_k < 1:
            raise ConfigError("Paper top_k must be a positive integer.")

    def snapshot(self):
        return {
            "schema_version": 5,
            "mode": "paper",
            "base_currency": "CAD",
            "initial_cash": str(self.initial_cash),
            "top_k": self.top_k,
            "limits": jsonable(self.limits),
            "costs": jsonable(self.costs),
        }


def load_paper_config(path: Path | None = None):
    try:
        raw = (
            path.read_bytes()
            if path
            else files("portfolio_research_desk").joinpath("resources/paper.toml").read_bytes()
        )
        values = tomllib.loads(raw.decode("utf-8"), parse_float=Decimal)
        _table(
            values,
            {"schema_version", "mode", "base_currency", "initial_cash", "top_k", "limits", "costs"},
            "paper config",
        )
        if type(values["schema_version"]) is not int or values["schema_version"] != 5:
            raise ConfigError("Paper schema_version must be integer 5.")
        if values["mode"] != "paper" or values["base_currency"] != "CAD":
            raise ConfigError("Phase 5 configuration requires paper mode and CAD base currency.")
        limits = _table(values["limits"], {f.name for f in fields(RiskLimits)}, "limits")
        costs = _table(values["costs"], {f.name for f in fields(Costs)}, "costs")
        integer_fields = {
            "max_positions",
            "max_order_shares",
            "max_quote_age_seconds",
            "max_fx_age_seconds",
        }
        limits = RiskLimits(
            **{k: v if k in integer_fields else _decimal(v, k) for k, v in limits.items()}
        )
        costs = Costs(**{k: _decimal(v, k) for k, v in costs.items()})
        return PaperConfig(
            _decimal(values["initial_cash"], "initial_cash"), values["top_k"], limits, costs
        )
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, DataError) as exc:
        raise ConfigError(f"Invalid paper configuration: {exc}") from exc
