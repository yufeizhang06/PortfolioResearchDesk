"""Strict orchestration settings; existing engine configuration schemas stay intact."""

import tomllib
from dataclasses import dataclass
from decimal import Decimal
from importlib.resources import files
from pathlib import Path

from portfolio_research_desk.errors import ConfigError, DataError
from portfolio_research_desk.paper_domain import money


@dataclass(frozen=True)
class WorkflowConfig:
    initial_cash_cad: Decimal = Decimal("3000.00")
    top_k: int = 2
    include_factors: bool = False
    include_ml: bool = False
    output_dir: Path = Path("outputs/workflows")

    def __post_init__(self):
        money(self.initial_cash_cad, "initial_cash_cad", positive=True)
        if type(self.top_k) is not int or not 1 <= self.top_k <= 3:
            raise ConfigError("Synthetic workflow top_k must be integer 1–3.")
        if type(self.include_factors) is not bool or type(self.include_ml) is not bool:
            raise ConfigError("include_factors and include_ml must be explicit booleans.")
        if not isinstance(self.output_dir, Path):
            raise ConfigError("output_dir must be a Path.")

    def snapshot(self):
        return {
            "schema_version": 6,
            "mode": "synthetic_demo",
            "initial_cash_cad": str(self.initial_cash_cad),
            "top_k": self.top_k,
            "include_factors": self.include_factors,
            "include_ml": self.include_ml,
            "output_dir": str(self.output_dir),
        }


def load_workflow_config(path: Path | None = None):
    try:
        raw = (
            path.read_bytes()
            if path
            else files("portfolio_research_desk").joinpath("resources/workflow.toml").read_bytes()
        )
        value = tomllib.loads(raw.decode("utf-8"), parse_float=Decimal)
        required = {
            "schema_version",
            "mode",
            "initial_cash_cad",
            "top_k",
            "include_factors",
            "include_ml",
            "output_dir",
        }
        if (
            set(value) != required
            or type(value["schema_version"]) is not int
            or value["schema_version"] != 6
            or value["mode"] != "synthetic_demo"
        ):
            raise ConfigError(
                "Workflow requires schema_version=6 / mode=synthetic_demo "
                "with the documented fields."
            )
        if type(value["initial_cash_cad"]) not in (str, int, Decimal):
            raise ConfigError("initial_cash_cad requires a decimal string or number.")
        if not isinstance(value["output_dir"], str) or not value["output_dir"].strip():
            raise ConfigError("output_dir must be a nonempty relative or absolute path.")
        base = path.resolve().parent if path else Path.cwd()
        return WorkflowConfig(
            Decimal(value["initial_cash_cad"]),
            value["top_k"],
            value["include_factors"],
            value["include_ml"],
            (base / value["output_dir"]).resolve(),
        )
    except (OSError, UnicodeError, ValueError, ArithmeticError, DataError) as exc:
        raise ConfigError(f"Cannot read workflow configuration: {exc}") from exc
