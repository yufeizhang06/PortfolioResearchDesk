"""Strict Phase 4 synthetic experiment settings; no real-data backtest switch."""

import tomllib
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path

from portfolio_research_desk.errors import ConfigError

MODELS = ("dummy", "logistic", "lasso", "random_forest", "xgboost")


@dataclass(frozen=True)
class MLConfig:
    schema_version: int = 4
    mode: str = "ml"
    expected_kind: str = "synthetic"
    sessions: int = 320
    horizon: int = 5
    min_train_dates: int = 100
    validation_dates: int = 20
    holdout_dates: int = 40
    gap_dates: int = 1
    embargo_dates: int = 1
    max_train_dates: int = 0
    inner_splits: int = 2
    inner_test_dates: int = 15
    seed: int = 42
    models: tuple[str, ...] = MODELS

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 4:
            raise ConfigError("ML schema_version must be integer 4.")
        if self.mode != "ml" or self.expected_kind != "synthetic":
            raise ConfigError("Phase 4 accepts ml / synthetic only; real PIT is unverified.")
        for name in (
            "sessions",
            "horizon",
            "min_train_dates",
            "validation_dates",
            "holdout_dates",
            "inner_splits",
            "inner_test_dates",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ConfigError(f"{name} must be a positive integer.")
        for name in ("gap_dates", "embargo_dates", "max_train_dates", "seed"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ConfigError(f"{name} must be a nonnegative integer.")
        if self.inner_splits < 2 or self.seed > 2**32 - 1:
            raise ConfigError("inner_splits >= 2 and seed <= 2**32-1 required.")
        if self.sessions < 60 + self.min_train_dates + self.validation_dates + self.holdout_dates:
            raise ConfigError("Insufficient sessions after 60-session feature warm-up.")
        minimum = (self.inner_splits + 1) * self.inner_test_dates + self.horizon + 2
        if self.min_train_dates < minimum:
            raise ConfigError("min_train_dates too small for purged nested validation.")
        if self.max_train_dates and self.max_train_dates < self.min_train_dates:
            raise ConfigError("Rolling max_train_dates must be >= min_train_dates (0 = expanding).")
        if (
            not isinstance(self.models, tuple)
            or not self.models
            or any(type(model) is not str or model not in MODELS for model in self.models)
            or len(set(self.models)) != len(self.models)
        ):
            raise ConfigError(f"models must be unique members of {MODELS}.")

    def snapshot(self):
        return asdict(self)


def load_ml_config(path: Path | None = None) -> MLConfig:
    try:
        raw = (
            path.read_bytes()
            if path
            else files("portfolio_research_desk").joinpath("resources/ml.toml").read_bytes()
        )
        values = tomllib.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError("Cannot read UTF-8 ML TOML.") from exc
    if set(values) - set(MLConfig.__dataclass_fields__):
        raise ConfigError("Unknown ML configuration fields.")
    if "models" in values:
        if not isinstance(values["models"], list):
            raise ConfigError("models must be a TOML array.")
        values["models"] = tuple(values["models"])
    return MLConfig(**values)
