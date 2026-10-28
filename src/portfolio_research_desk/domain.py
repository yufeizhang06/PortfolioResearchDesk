"""Immutable contracts shared by strategy, portfolio and simulation services."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from portfolio_research_desk.errors import DataError, ExecutionError

ZERO = Decimal("0")
ONE = Decimal("1")
CENT = Decimal("0.01")
BPS = Decimal("10000")


def require_utc(value: datetime) -> None:
    """Require explicit UTC rather than guessing the timezone of naive input."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise DataError("All timestamps must be timezone-aware UTC.")


def jsonable(value: Any) -> Any:
    """Serialize Decimal as strings, preserving money precision in JSON/CSV."""
    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(item) for item in value]
    return value


def fingerprint(value: Any) -> str:
    encoded = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, order=True)
class AssetId:
    market: str
    exchange: str
    symbol: str
    currency: str

    def __post_init__(self) -> None:
        if not all(isinstance(x, str) and x for x in (self.market, self.exchange, self.symbol)):
            raise DataError("Asset identity must include market, exchange and symbol.")
        if not re.fullmatch(r"[A-Z][A-Z0-9_.-]*", self.symbol):
            raise DataError("Asset symbols must be normalized uppercase identifiers.")
        if not re.fullmatch(r"[A-Z]{3}", self.currency):
            raise DataError("Asset currency must be an explicit three-letter code.")


@dataclass(frozen=True)
class TradingSession:
    session_date: date
    open_at: datetime
    close_at: datetime

    @property
    def decision_at(self) -> datetime:
        """Fixture policy: decision two minutes after the scheduled close."""
        return self.close_at + timedelta(minutes=2)

    def __post_init__(self) -> None:
        require_utc(self.open_at)
        require_utc(self.close_at)
        if not self.open_at < self.close_at or self.open_at.date() != self.session_date:
            raise DataError("Invalid session schedule.")
        if self.close_at.date() != self.session_date:
            raise DataError("Session close date does not match session_date.")


@dataclass(frozen=True)
class PriceBar:
    asset: AssetId
    session_date: date
    open_at: datetime
    event_time: datetime
    observation_end: datetime
    available_at: datetime
    open: Decimal | None
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    tradable: bool
    adjusted: bool = False
    source: str = "synthetic_v1"

    def __post_init__(self) -> None:
        for stamp in (self.open_at, self.event_time, self.observation_end, self.available_at):
            require_utc(stamp)
        if not (self.open_at < self.event_time == self.observation_end <= self.available_at):
            raise DataError("Invalid event/observation/available timestamps.")
        if self.open_at.date() != self.session_date or self.event_time.date() != self.session_date:
            raise DataError("Bar timestamps do not match the session date.")
        prices = [self.high, self.low, self.close] + ([] if self.open is None else [self.open])
        if any(not p.is_finite() or p <= 0 or p > Decimal("1e12") for p in prices):
            raise DataError("OHLC must be finite positive prices at most 1e12.")
        if any(p != p.quantize(CENT) for p in prices):
            raise DataError("Phase 1 requires cent-denominated USD prices.")
        if not self.low <= self.close <= self.high:
            raise DataError("Invalid close/high/low bounds.")
        if self.open is not None and not self.low <= self.open <= self.high:
            raise DataError("Invalid open/high/low bounds.")
        if type(self.volume) is not int or self.volume < 0:
            raise DataError("Volume must be a nonnegative integer.")
        if type(self.tradable) is not bool or type(self.adjusted) is not bool:
            raise DataError("tradable and adjusted must be explicit booleans.")


@dataclass(frozen=True)
class UniverseSnapshot:
    universe_id: str
    as_of: datetime
    membership_type: str
    assets: tuple[AssetId, ...]
    source: str
    available_at: datetime | None = None
    synthetic: bool | None = None
    limitations: tuple[str, ...] = ()
    screening_applied: bool = False
    point_in_time_verified: bool = False

    def __post_init__(self) -> None:
        require_utc(self.as_of)
        if self.membership_type not in {"user_static", "current_snapshot", "point_in_time"}:
            raise DataError("Unknown universe membership type.")
        if not self.assets and not self.screening_applied:
            raise DataError("A base universe must be nonempty.")
        if self.available_at is not None:
            require_utc(self.available_at)
        if self.synthetic is not None and type(self.synthetic) is not bool:
            raise DataError("Universe synthetic marker must be an explicit boolean.")
        if len(set(self.assets)) != len(self.assets):
            raise DataError("Universe assets must be unique.")


@dataclass(frozen=True)
class Signal:
    asset: AssetId
    decision_at: datetime
    observation_start: datetime
    observation_end: datetime
    available_at: datetime
    score: Decimal

    def __post_init__(self) -> None:
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
            raise DataError("Signal inputs are not available at decision_at.")
        if not self.score.is_finite():
            raise DataError("Signal score must be finite.")


@dataclass(frozen=True)
class TargetPortfolio:
    decision_at: datetime
    weights: tuple[tuple[AssetId, Decimal], ...]
    cash_weight: Decimal

    def __post_init__(self) -> None:
        require_utc(self.decision_at)
        weights = [weight for _, weight in self.weights] + [self.cash_weight]
        if any(not w.is_finite() or not ZERO <= w <= ONE for w in weights):
            raise ExecutionError("Target weights must be finite and long-only.")
        if abs(sum(weights, ZERO) - ONE) > Decimal("1e-24"):
            raise ExecutionError("Target asset and cash weights must sum to one.")
        if len({asset for asset, _ in self.weights}) != len(self.weights):
            raise ExecutionError("Duplicate assets in target portfolio.")


@dataclass(frozen=True)
class Position:
    asset: AssetId
    quantity: int

    def __post_init__(self) -> None:
        if type(self.quantity) is not int or self.quantity <= 0:
            raise ExecutionError("Positions must contain positive integer shares.")


@dataclass(frozen=True)
class PortfolioState:
    as_of: datetime
    cash: Decimal
    positions: tuple[Position, ...] = ()
    currency: str = "USD"

    def __post_init__(self) -> None:
        require_utc(self.as_of)
        if not self.cash.is_finite() or self.cash < 0 or self.cash != self.cash.quantize(CENT):
            raise ExecutionError("Cash must be nonnegative and denominated in cents.")
        if self.currency != "USD" or any(p.asset.currency != self.currency for p in self.positions):
            raise ExecutionError("Phase 1 portfolio is USD-only; FX is not implemented.")
        if len({p.asset for p in self.positions}) != len(self.positions):
            raise ExecutionError("Duplicate position identities.")

    def holdings(self) -> dict[AssetId, int]:
        return {p.asset: p.quantity for p in self.positions}


@dataclass(frozen=True)
class OrderProposal:
    order_id: str
    asset: AssetId
    side: str
    quantity: int
    decision_at: datetime
    reference_price: Decimal

    def __post_init__(self) -> None:
        require_utc(self.decision_at)
        if self.side not in {"BUY", "SELL"} or type(self.quantity) is not int or self.quantity <= 0:
            raise ExecutionError("Orders require a valid side and positive integer quantity.")
        if not self.reference_price.is_finite() or self.reference_price <= 0:
            raise ExecutionError("Order reference price must be positive and finite.")
        if not self.order_id:
            raise ExecutionError("Order ID is required.")


@dataclass(frozen=True)
class Fill:
    order_id: str
    asset: AssetId
    side: str
    quantity: int
    decision_at: datetime
    execution_at: datetime
    raw_price: Decimal
    price: Decimal
    commission: Decimal
    slippage_cost: Decimal


@dataclass(frozen=True)
class OrderOutcome:
    order: OrderProposal
    execution_at: datetime | None
    filled_quantity: int
    status: str
    reason: str


@dataclass(frozen=True)
class PositionValue:
    asset: AssetId
    quantity: int
    close: Decimal
    market_value: Decimal
    weight: Decimal


@dataclass(frozen=True)
class EquityPoint:
    session_date: date
    valuation_at: datetime
    cash: Decimal
    nav: Decimal
    positions: tuple[PositionValue, ...]
    cumulative_commission: Decimal
    cumulative_slippage: Decimal
    cash_benchmark_nav: Decimal
