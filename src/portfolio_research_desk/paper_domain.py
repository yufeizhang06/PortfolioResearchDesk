"""CAD paper contracts; deliberately separate from the legacy USD backtest state."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Context, Decimal, localcontext
from functools import wraps

from portfolio_research_desk.domain import CENT, ZERO, AssetId, require_utc
from portfolio_research_desk.errors import DataError, ExecutionError

CURRENCIES = ("CAD", "USD")


def accounting(function):
    """Isolate every public calculation from the caller's Decimal context."""

    @wraps(function)
    def wrapped(*args, **kwargs):
        with localcontext(Context(prec=50)):
            return function(*args, **kwargs)

    return wrapped


def number(value, name, minimum=ZERO, maximum=Decimal("1e12")):
    if not isinstance(value, Decimal) or not value.is_finite() or not minimum <= value <= maximum:
        raise DataError(f"{name} must be a finite Decimal in [{minimum}, {maximum}].")


@accounting
def money(value, name, positive=False):
    number(value, name, CENT if positive else ZERO)
    if value != value.quantize(CENT):
        raise DataError(f"{name} must be whole cents.")


def supported(asset):
    if not isinstance(asset, AssetId) or asset.currency not in CURRENCIES:
        raise DataError("Only explicit CAD/USD asset identities are supported.")


@dataclass(frozen=True)
class Quote:
    asset: AssetId
    observed_at: datetime
    available_at: datetime
    price: Decimal
    kind: str = "close"
    tradable: bool = True
    volume: int = 1
    adjusted: bool = False
    source: str = "synthetic_phase5"
    synthetic: bool = True

    def __post_init__(self):
        supported(self.asset)
        require_utc(self.observed_at)
        require_utc(self.available_at)
        money(self.price, "quote price", positive=True)
        if self.observed_at > self.available_at or self.kind not in {"open", "close", "mark"}:
            raise DataError("Invalid quote timestamps or kind.")
        if type(self.tradable) is not bool or type(self.synthetic) is not bool:
            raise DataError("Quote flags must be explicit booleans.")
        if self.adjusted is not False:
            raise DataError(
                "CAD ledger requires raw prices; adjusted prices would double count actions."
            )
        if type(self.volume) is not int or self.volume < 0 or not self.source:
            raise DataError("Quote requires nonnegative integer volume and source.")


@dataclass(frozen=True)
class Sector:
    asset: AssetId
    name: str
    effective_at: datetime
    available_at: datetime

    def __post_init__(self):
        supported(self.asset)
        require_utc(self.effective_at)
        require_utc(self.available_at)
        if not isinstance(self.name, str) or not self.name.strip():
            raise DataError("Sector classification must be explicit.")


@dataclass(frozen=True)
class Costs:
    fixed_fee: Decimal = Decimal("0.10")
    commission_bps: Decimal = Decimal("5")
    slippage_bps: Decimal = Decimal("10")
    fx_fee_bps: Decimal = Decimal("20")

    def __post_init__(self):
        money(self.fixed_fee, "fixed_fee")
        for name in ("commission_bps", "slippage_bps", "fx_fee_bps"):
            number(getattr(self, name), name, maximum=Decimal("9999"))


@dataclass(frozen=True)
class Holding:
    asset: AssetId
    quantity: int
    cost_local: Decimal
    cost_cad: Decimal

    def __post_init__(self):
        supported(self.asset)
        if type(self.quantity) is not int or not 0 < self.quantity <= 10**12:
            raise ExecutionError("Holdings require positive integer shares at most 1e12.")
        number(self.cost_local, "cost_local", maximum=Decimal("1e30"))
        number(self.cost_cad, "cost_cad", maximum=Decimal("1e30"))


@dataclass(frozen=True)
class CADState:
    as_of: datetime
    cash: tuple[tuple[str, Decimal], ...] = (("CAD", ZERO), ("USD", ZERO))
    positions: tuple[Holding, ...] = ()
    net_contributions_cad: Decimal = ZERO
    commission_cad: Decimal = ZERO
    fx_cost_cad: Decimal = ZERO
    slippage_cad: Decimal = ZERO
    realized_pnl_cad: Decimal = ZERO
    dividends_cad: Decimal = ZERO

    def __post_init__(self):
        require_utc(self.as_of)
        if tuple(c for c, _ in self.cash) != CURRENCIES:
            raise ExecutionError("Cash must contain exactly CAD then USD; base currency is CAD.")
        for currency, amount in self.cash:
            money(amount, f"{currency} cash")
        if len({p.asset for p in self.positions}) != len(self.positions):
            raise ExecutionError("Duplicate holding identities.")
        for name in ("commission_cad", "fx_cost_cad", "slippage_cad", "dividends_cad"):
            number(getattr(self, name), name, maximum=Decimal("1e30"))
        for name in ("net_contributions_cad", "realized_pnl_cad"):
            number(getattr(self, name), name, -Decimal("1e30"), Decimal("1e30"))

    def balances(self):
        return dict(self.cash)

    def holdings(self):
        return {p.asset: p for p in self.positions}
