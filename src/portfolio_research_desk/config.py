"""Strict Phase 0 TOML configuration, with no optional runtime dependencies."""

import tomllib
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path

from portfolio_research_desk.errors import ConfigError


@dataclass(frozen=True)
class AppConfig:
    """Only implemented settings belong in this schema."""

    schema_version: int
    mode: str
    data_source: str
    currency: str
    log_level: str = "INFO"

    def snapshot(self) -> dict[str, int | str]:
        """Return a normalized, JSON-serializable configuration."""
        return asdict(self)


def load_config(path: Path | None = None) -> AppConfig:
    """Load an explicit file, or the packaged offline default.

    There is no environment-variable or working-directory fallback. Unsupported
    modes, currencies, unknown keys and implicit type coercion are rejected.
    """
    try:
        if path is None:
            raw = files("portfolio_research_desk").joinpath("resources/default.toml").read_bytes()
        else:
            raw = path.read_bytes()
        values = tomllib.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError("Cannot read UTF-8 TOML configuration.") from exc

    required = {"schema_version", "mode", "data_source", "currency"}
    allowed = required | {"log_level"}
    if unknown := values.keys() - allowed:
        raise ConfigError(f"Unknown config fields: {', '.join(sorted(unknown))}.")
    if missing := required - values.keys():
        raise ConfigError(f"Missing config fields: {', '.join(sorted(missing))}.")
    if type(values["schema_version"]) is not int or values["schema_version"] != 1:
        raise ConfigError("schema_version must be integer 1.")
    for field in ("mode", "data_source", "currency", "log_level"):
        if field in values and type(values[field]) is not str:
            raise ConfigError(f"{field} must be a string.")
    if values["mode"] != "offline_sample":
        raise ConfigError("Phase 0 supports mode='offline_sample' only; no backtest or paper mode.")
    if values["data_source"] != "synthetic":
        raise ConfigError("Phase 0 supports data_source='synthetic' only.")
    if values["currency"] != "USD":
        raise ConfigError("Phase 0 sample is USD-only; CAD/FX and accounts are not implemented.")
    if values.get("log_level", "INFO") not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
        raise ConfigError("log_level must be DEBUG, INFO, WARNING or ERROR.")
    return AppConfig(**values)
