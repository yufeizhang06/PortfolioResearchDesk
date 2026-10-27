"""Past-only momentum baseline; no fitted model or future labels."""

from datetime import datetime

from portfolio_research_desk.domain import AssetId, PriceBar, Signal, require_utc
from portfolio_research_desk.errors import DataError


def momentum_signals(
    bars: tuple[PriceBar, ...],
    assets: tuple[AssetId, ...],
    decision_at: datetime,
    lookback: int,
) -> tuple[Signal, ...]:
    """Score close[t]/close[t-L]-1 using only the known trailing window."""
    require_utc(decision_at)
    if type(lookback) is not int or lookback < 1:
        raise DataError("Momentum lookback must be a positive session count.")
    signals = []
    for asset in assets:
        history = sorted(
            (b for b in bars if b.asset == asset and b.observation_end <= decision_at),
            key=lambda b: b.observation_end,
        )
        if len(history) < lookback + 1:
            raise DataError(f"Insufficient momentum history for {asset.symbol}.")
        window = history[-lookback - 1 :]
        if any(b.available_at > decision_at for b in window):
            raise DataError(f"Momentum input is not available at decision time: {asset.symbol}.")
        signals.append(
            Signal(
                asset,
                decision_at,
                window[0].observation_end,
                window[-1].observation_end,
                max(b.available_at for b in window),
                window[-1].close / window[0].close - 1,
            )
        )
    return tuple(signals)
