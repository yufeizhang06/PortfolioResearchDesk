"""Small UI-independent application contracts; financial types stay in the domain."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from portfolio_research_desk.domain import AssetId


@dataclass(frozen=True)
class HistoryRequest:
    assets: tuple[AssetId, ...]
    start: date
    end: date
    source: str = "synthetic"
    local_file: Path | None = None
    expected_kind: str = "synthetic"
    network_allowed: bool = False
    refresh: bool = False
    allow_stale: bool = False


@dataclass(frozen=True)
class FactorRequest:
    history_file: str
    start: date
    end: date
    frequency: str = "daily"
    source: str = "synthetic"
    ff3_file: Path | None = None
    momentum_file: Path | None = None
    sessions_file: Path | None = None
    covariance: str = "HC3"
    confidence: float = 0.95
    min_obs: int = 20
    rolling_window: int = 32
    return_basis: str = "adjusted_close"


@dataclass(frozen=True)
class TaskRef:
    command_id: str
    kind: str
    status: str
    generated_at: str
    directory: str
    data_kind: str
