"""Reusable Phase 3 service, sharing Phase 2 data acquisition and provenance."""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from importlib.resources import files

from portfolio_research_desk.data_adapters import LocalHistoryAdapter
from portfolio_research_desk.data_contracts import History, validate_quality
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.factor_analysis import (
    compare_models,
    require_factor_dependencies,
    rolling_exposures,
)
from portfolio_research_desk.factor_config import FactorConfig
from portfolio_research_desk.factor_data import FactorData, FrenchAdapter, combine_factors
from portfolio_research_desk.factor_returns import (
    AlignedSample,
    ReturnData,
    align_common_sample,
    calculate_returns,
)
from portfolio_research_desk.research_config import load_research_config
from portfolio_research_desk.research_workflow import run_research


@dataclass(frozen=True)
class FactorRun:
    config: FactorConfig
    factors: FactorData
    history: History
    returns: ReturnData
    sample: AlignedSample
    comparison: dict | None
    rolling: tuple[dict, ...]
    cache_events: tuple[dict, ...]
    quality: dict
    status: str
    warnings: tuple[str, ...]


def run_factor_research(
    config: FactorConfig, clock=lambda: datetime.now(UTC), factor_adapter=None
) -> FactorRun:
    require_factor_dependencies()
    resource = files("portfolio_research_desk").joinpath("resources")
    cache_events = []
    if config.factor_source == "french":
        adapter = factor_adapter or FrenchAdapter(config.cache_dir, clock=clock)
        factors, event = adapter.fetch(config.frequency, config.offline, False, config.allow_stale)
        cache_events.append(event)
    else:
        synthetic = config.factor_source == "synthetic"
        try:
            ff3 = (
                resource.joinpath("factors_ff3.csv").read_bytes()
                if synthetic
                else config.ff3_file.read_bytes()
            )
            mom = (
                resource.joinpath("factors_mom.csv").read_bytes()
                if synthetic
                else config.momentum_file.read_bytes()
            )
        except OSError as exc:
            raise DataError("Cannot read local French-format factors.") from exc
        labelled = (
            b"PortfolioResearchDesk synthetic" in ff3 or b"PortfolioResearchDesk synthetic" in mom
        )
        if labelled and config.expected_kind != "synthetic":
            raise DataError("Synthetic factor files cannot be relabelled real.")
        factors = combine_factors(
            ff3,
            mom,
            config.frequency,
            datetime(2024, 6, 1, tzinfo=UTC) if synthetic else clock(),
            "PortfolioResearchDesk synthetic fixture"
            if synthetic
            else f"local:{config.ff3_file} | {config.momentum_file}",
            config.expected_kind == "synthetic",
        )
    if config.research_config:
        settings = load_research_config(config.research_config)
        settings = replace(
            settings,
            offline=config.offline or settings.offline,
            allow_stale=config.allow_stale or settings.allow_stale,
        )
        acquired = run_research(settings, "data", clock=clock)
        candidates = [
            h
            for h in acquired.histories
            if not config.asset_symbol or h.rows[0].asset.symbol == config.asset_symbol
        ]
        if len(candidates) != 1:
            raise DataError(
                "Select exactly one acquired history using asset_symbol. Data failures: "
                + str(acquired.failures)
            )
        history = candidates[0]
        cache_events.extend(acquired.cache_events)
    else:
        from pathlib import Path

        history = LocalHistoryAdapter(
            config.price_file or Path(str(resource.joinpath("factor_prices.csv")))
        ).read()
    if config.asset_symbol and any(r.asset.symbol != config.asset_symbol for r in history.rows):
        raise DataError("Local/acquired history does not match asset_symbol.")
    if history.data_kind != config.expected_kind or factors.synthetic != (
        config.expected_kind == "synthetic"
    ):
        raise DataError("Factor/price data kind differs from expected_kind.")
    sessions = None
    if config.sessions_file:
        try:
            sessions = tuple(
                date.fromisoformat(line.strip())
                for line in config.sessions_file.read_text("utf-8").splitlines()
                if line.strip()
            )
        except (OSError, ValueError) as exc:
            raise DataError("sessions_file must contain one ISO session date per line.") from exc
    returns = calculate_returns(history, factors, config.return_basis, sessions)
    sample = align_common_sample(returns, factors, config.start, config.end)
    options = {
        "covariance": config.covariance,
        "min_obs": config.min_obs,
        "confidence": config.confidence,
    }
    notes = [
        *returns.warnings,
        "Ex-post attribution only; retrieved/revised factors cannot enter trading signals.",
        "Alpha is per observation period; statistical significance is not tradable excess return.",
        "FF3/FF4 both use the same complete four-factor sample, response and likelihood.",
    ]
    try:
        comparison = compare_models(sample, **options)
        status = "complete"
    except DataError as exc:
        notes.append(str(exc))
        comparison, status = None, "failed"
    rolling = rolling_exposures(sample, config.rolling_window, **options)
    if not rolling:
        notes.append("ROLLING_INSUFFICIENT_PERIODS: no full nominal window is available.")
    if any(r["status"] == "failed" for r in rolling):
        notes.append(
            "ROLLING_WINDOW_FAILURES: inspect per-window reasons; failed estimates are not filled."
        )
    if sample.exclusions:
        notes.append(f"Excluded {len(sample.exclusions)} periods; see alignment diagnostics.")
    from portfolio_research_desk.domain import jsonable

    return FactorRun(
        config,
        factors,
        history,
        returns,
        sample,
        comparison,
        rolling,
        tuple(cache_events),
        {"prices": jsonable(validate_quality(history)), "declared_sessions": jsonable(sessions)},
        status,
        tuple(notes),
    )
