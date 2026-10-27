"""Strict Phase 3 TOML; preserves earlier configuration schemas."""

import math
import tomllib
from dataclasses import dataclass
from datetime import date
from importlib.resources import files
from pathlib import Path

from portfolio_research_desk.domain import jsonable
from portfolio_research_desk.errors import ConfigError


@dataclass(frozen=True)
class FactorConfig:
    frequency: str
    factor_source: str
    expected_kind: str
    start: date
    end: date
    return_basis: str = "adjusted_close"
    price_file: Path | None = None
    research_config: Path | None = None
    asset_symbol: str | None = None
    ff3_file: Path | None = None
    momentum_file: Path | None = None
    sessions_file: Path | None = None
    min_obs: int = 20
    rolling_window: int = 60
    covariance: str = "HC3"
    confidence: float = 0.95
    offline: bool = True
    allow_stale: bool = False
    cache_dir: Path = Path("data/cache/factors")
    output_dir: Path = Path("outputs/factors")

    def __post_init__(self):
        if self.frequency not in {"daily", "monthly"}:
            raise ConfigError("Factor frequency must be daily or monthly.")
        if self.factor_source not in {"synthetic", "local", "french"}:
            raise ConfigError("factor_source must be synthetic, local or french.")
        if (
            self.expected_kind not in {"real", "synthetic"}
            or (self.factor_source == "synthetic" and self.expected_kind != "synthetic")
            or (self.factor_source == "french" and self.expected_kind != "real")
        ):
            raise ConfigError("Factor source and expected_kind conflict.")
        if type(self.start) is not date or type(self.end) is not date or self.start >= self.end:
            raise ConfigError("Require date start < exclusive end.")
        if self.return_basis not in {"close", "adjusted_close"}:
            raise ConfigError("return_basis must be close or adjusted_close.")
        if self.covariance not in {"nonrobust", "HC3"}:
            raise ConfigError("covariance must be nonrobust or HC3.")
        if type(self.min_obs) is not int or self.min_obs < 6:
            raise ConfigError("min_obs must be an integer >=6.")
        if type(self.rolling_window) is not int or self.rolling_window < self.min_obs:
            raise ConfigError("rolling_window must be an integer >= min_obs.")
        if (
            type(self.confidence) not in {float, int}
            or not math.isfinite(self.confidence)
            or not 0 < self.confidence < 1
        ):
            raise ConfigError("confidence must be finite and in (0,1).")
        if type(self.offline) is not bool or type(self.allow_stale) is not bool:
            raise ConfigError("offline/allow_stale must be booleans.")
        if self.price_file and self.research_config:
            raise ConfigError("Choose price_file or research_config, not both.")
        if self.factor_source != "synthetic" and not (self.price_file or self.research_config):
            raise ConfigError(
                "Real/local research needs native price_file or Phase 2 research_config."
            )
        if self.factor_source == "local" and not (self.ff3_file and self.momentum_file):
            raise ConfigError("Local factors require ff3_file and momentum_file.")
        if self.factor_source != "local" and (self.ff3_file or self.momentum_file):
            raise ConfigError("Factor file paths apply to local source only.")
        if self.factor_source == "synthetic" and self.frequency != "daily":
            raise ConfigError("Packaged synthetic fixture is daily only.")
        if self.frequency == "monthly" and not self.sessions_file:
            raise ConfigError(
                "Monthly price returns require sessions_file, including the prior month."
            )

    def snapshot(self):
        return jsonable(
            {
                "schema_version": 3,
                **{k: str(v) if isinstance(v, Path) else v for k, v in self.__dict__.items()},
            }
        )


def load_factor_config(path: Path | None = None) -> FactorConfig:
    try:
        raw = (
            path.read_bytes()
            if path
            else files("portfolio_research_desk").joinpath("resources/factors.toml").read_bytes()
        )
        values = tomllib.loads(raw.decode("utf-8"))
        version = values.pop("schema_version", None)
        if type(version) is not int or version != 3:
            raise ConfigError("Factor schema_version must be integer 3.")
        allowed = FactorConfig.__dataclass_fields__.keys()
        if values.keys() - allowed:
            raise ConfigError("Unknown factor configuration fields.")
        base = path.resolve().parent if path else Path.cwd()
        for name in (
            "price_file",
            "research_config",
            "ff3_file",
            "momentum_file",
            "sessions_file",
            "cache_dir",
            "output_dir",
        ):
            if name in values:
                if type(values[name]) is not str or not values[name]:
                    raise ConfigError(f"{name} must be a nonempty path string.")
                values[name] = (base / values[name]).resolve()
        for name in ("start", "end"):
            if type(values.get(name)) is str:
                values[name] = date.fromisoformat(values[name])
        for name in (
            "frequency",
            "factor_source",
            "expected_kind",
            "return_basis",
            "covariance",
            "asset_symbol",
        ):
            if name in values and type(values[name]) is not str:
                raise ConfigError(f"{name} must be a string.")
        return FactorConfig(**values)
    except (OSError, UnicodeError, ValueError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError("Cannot load strict Phase 3 factor configuration.") from exc
