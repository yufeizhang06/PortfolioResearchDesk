"""Past-only price features and next-open forward labels on declared synthetic panels."""

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Context, Decimal, localcontext
from statistics import mean, stdev

from portfolio_research_desk.domain import AssetId, PriceBar, TradingSession, require_utc
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.market_data import MarketDataset, validate_dataset

FEATURE_NAMES = (
    "return_5",
    "return_20",
    "return_60",
    "volatility_20",
    "volatility_60",
    "log_dollar_volume_20",
    "relative_return_20",
)


@dataclass(frozen=True)
class FeatureRow:
    asset: AssetId
    decision_at: datetime
    observation_start: datetime
    observation_end: datetime
    available_at: datetime
    values: tuple[float, ...]
    source: str = "synthetic_price_features_v1"

    def __post_init__(self):
        for stamp in (
            self.decision_at,
            self.observation_start,
            self.observation_end,
            self.available_at,
        ):
            require_utc(stamp)
        if (
            not self.observation_start
            <= self.observation_end
            <= self.available_at
            <= self.decision_at
        ):
            raise DataError("Feature input is future or unavailable at decision time.")
        if self.source != "synthetic_price_features_v1":
            raise DataError("Unverified feature provenance; Phase 3 factors cannot enter signals.")
        if len(self.values) != len(FEATURE_NAMES) or any(not math.isfinite(x) for x in self.values):
            raise DataError("Features require the fixed finite feature schema.")


@dataclass(frozen=True)
class LabelRow:
    asset: AssetId
    decision_at: datetime
    start_at: datetime
    end_at: datetime
    known_at: datetime
    forward_return: float

    @property
    def target(self) -> int:
        return int(self.forward_return > 0)

    def __post_init__(self):
        for stamp in (self.decision_at, self.start_at, self.end_at, self.known_at):
            require_utc(stamp)
        if not self.decision_at < self.start_at < self.end_at <= self.known_at:
            raise DataError("Invalid forward label interval/known_at.")
        if not math.isfinite(self.forward_return) or self.forward_return <= -1:
            raise DataError("Invalid forward return.")


@dataclass(frozen=True)
class Sample:
    feature: FeatureRow
    label: LabelRow | None

    def __post_init__(self):
        if self.label and (self.feature.asset, self.feature.decision_at) != (
            self.label.asset,
            self.label.decision_at,
        ):
            raise DataError("Feature/label identity or decision mismatch.")


def synthetic_ml_dataset(count: int = 320) -> MarketDataset:
    """Fixed integer arithmetic, no RNG or market calendar claims; v1 generator."""
    with localcontext(Context(prec=28)):
        return _synthetic_ml_dataset(count)


def _synthetic_ml_dataset(count: int) -> MarketDataset:
    if type(count) is not int or count < 3:
        raise DataError("Synthetic session count must be >=3.")
    sessions, bars = [], []
    day = date(2020, 1, 2)
    prices = [10000, 8500, 12000]
    for index in range(count):
        while day.weekday() >= 5:
            day += timedelta(days=1)
        session = TradingSession(
            day,
            datetime(day.year, day.month, day.day, 14, 30, tzinfo=UTC),
            datetime(day.year, day.month, day.day, 21, tzinfo=UTC),
        )
        sessions.append(session)
        for asset_index in range(3):
            asset = AssetId("US", "SYNTHETIC", f"SYN_{chr(65 + asset_index)}", "USD")
            opening = max(100, prices[asset_index] + ((index * 7 + asset_index * 11) % 29) - 14)
            change = ((index * (13 + asset_index * 4) + asset_index * 23) % 97) - 48
            change += 14 if ((index // 19 + asset_index) % 2) else -9
            close = max(100, opening + change)
            prices[asset_index] = close
            bars.append(
                PriceBar(
                    asset,
                    day,
                    session.open_at,
                    session.close_at,
                    session.close_at,
                    session.close_at + timedelta(minutes=1),
                    Decimal(opening) / 100,
                    Decimal(max(opening, close) + 30) / 100,
                    Decimal(min(opening, close) - 30) / 100,
                    Decimal(close) / 100,
                    100000 + ((index * 37 + asset_index * 997) % 50000),
                    True,
                )
            )
        day += timedelta(days=1)
    result = MarketDataset(tuple(bars), tuple(sessions))
    validate_dataset(result)
    return result


def build_samples(dataset: MarketDataset, horizon: int = 5) -> tuple[Sample, ...]:
    with localcontext(Context(prec=28)):
        return _build_samples(dataset, horizon)


def _build_samples(dataset: MarketDataset, horizon: int) -> tuple[Sample, ...]:
    validate_dataset(dataset)
    if type(horizon) is not int or horizon < 1:
        raise DataError("Label horizon must be positive.")
    if len(dataset.sessions) < 62:
        raise DataError("At least 62 sessions required for features.")
    assets = sorted({bar.asset for bar in dataset.bars})
    by_asset = {
        a: sorted((b for b in dataset.bars if b.asset == a), key=lambda b: b.session_date)
        for a in assets
    }
    result = []
    for index in range(60, len(dataset.sessions)):
        session = dataset.sessions[index]
        # The cross-sectional market proxy uses this fixed synthetic universe only.
        dependencies = [b for a in assets for b in by_asset[a][index - 60 : index + 1]]
        available = max(b.available_at for b in dependencies)
        market = mean(
            float(by_asset[a][index].close / by_asset[a][index - 20].close - 1) for a in assets
        )
        for asset in assets:
            history = by_asset[asset]
            window = history[index - 60 : index + 1]
            returns = [
                float(b.close / a.close - 1) for a, b in zip(window, window[1:], strict=False)
            ]
            momentum = [
                float(window[-1].close / history[index - lag].close - 1) for lag in (5, 20, 60)
            ]
            liquidity = mean(float(b.close * b.volume) for b in window[-20:])
            feature = FeatureRow(
                asset,
                session.decision_at,
                window[0].observation_end,
                window[-1].observation_end,
                available,
                (
                    *momentum,
                    stdev(returns[-20:]),
                    stdev(returns),
                    math.log1p(liquidity),
                    momentum[1] - market,
                ),
            )
            label = None
            if index + horizon + 1 < len(history):
                entry, exit_bar = history[index + 1], history[index + horizon + 1]
                if (
                    entry.open is not None
                    and exit_bar.open is not None
                    and entry.tradable
                    and exit_bar.tradable
                    and entry.volume > 0
                    and exit_bar.volume > 0
                ):
                    label = LabelRow(
                        asset,
                        session.decision_at,
                        entry.open_at,
                        exit_bar.open_at,
                        max(entry.available_at, exit_bar.available_at),
                        float(exit_bar.open / entry.open - 1),
                    )
            result.append(Sample(feature, label))
    return tuple(result)
