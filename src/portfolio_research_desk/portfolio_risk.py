"""Transparent concentration, cash and trading constraints, valued in CAD."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from portfolio_research_desk.domain import ONE, ZERO
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.fx import FXBook, FXRate, rate_for
from portfolio_research_desk.paper_domain import CADState, Quote, Sector, accounting, number


@dataclass(frozen=True)
class RiskLimits:
    max_positions: int = 10
    max_position_weight: Decimal = Decimal("0.20")
    max_sector_weight: Decimal = Decimal("0.40")
    cash_buffer: Decimal = Decimal("0.05")
    max_trade_weight: Decimal = Decimal("0.25")
    max_turnover: Decimal = ONE
    min_trade_cad: Decimal = ONE
    max_order_shares: int = 100000
    max_price_deviation: Decimal = Decimal("0.20")
    max_quote_age_seconds: int = 604800
    max_fx_age_seconds: int = 604800

    def __post_init__(self):
        for name in (
            "max_positions",
            "max_order_shares",
            "max_quote_age_seconds",
            "max_fx_age_seconds",
        ):
            if type(getattr(self, name)) is not int or not 1 <= getattr(self, name) <= 10**9:
                raise DataError(f"{name} must be a positive integer.")
        for name in (
            "max_position_weight",
            "max_sector_weight",
            "max_trade_weight",
            "max_turnover",
        ):
            number(getattr(self, name), name, Decimal("1e-12"), ONE)
        for name in ("cash_buffer", "max_price_deviation"):
            number(getattr(self, name), name, ZERO, ONE)
        number(self.min_trade_cad, "min_trade_cad")

    @property
    def fx_age(self):
        return timedelta(seconds=self.max_fx_age_seconds)


@dataclass(frozen=True)
class MarketSnapshot:
    quotes: tuple[Quote, ...]
    fx: FXBook = FXBook()
    sectors: tuple[Sector, ...] = ()

    def __post_init__(self):
        if (
            not isinstance(self.quotes, tuple)
            or any(not isinstance(q, Quote) for q in self.quotes)
            or not isinstance(self.fx, FXBook)
            or not isinstance(self.sectors, tuple)
            or any(not isinstance(s, Sector) for s in self.sectors)
        ):
            raise DataError("Snapshot requires Quote, FXBook and Sector contracts.")
        if len({q.asset for q in self.quotes}) != len(self.quotes):
            raise DataError("Snapshot requires one unique quote per asset.")
        if len({s.asset for s in self.sectors}) != len(self.sectors):
            raise DataError("Snapshot requires one unique sector per asset.")

    def known_quotes(self, at, limits):
        for quote in self.quotes:
            if not quote.observed_at <= quote.available_at <= at:
                raise DataError("Quote is unavailable at valuation/decision/execution time.")
            if (at - quote.observed_at).total_seconds() > limits.max_quote_age_seconds:
                raise DataError("Stale price quote.")
        return {q.asset: q for q in self.quotes}

    def known_sectors(self, assets, at):
        records = {s.asset: s for s in self.sectors}
        result = {}
        for asset in assets:
            record = records.get(asset)
            if record is None or record.effective_at > at or record.available_at > at:
                raise DataError("Missing/unavailable sector; concentration cannot be verified.")
            result[asset] = record.name
        return result


@dataclass(frozen=True)
class Valuation:
    as_of: datetime
    nav_cad: Decimal
    cash_cad: Decimal
    positions: tuple[dict, ...]
    cash_weight: Decimal
    sector_weights: tuple[tuple[str, Decimal], ...]
    violations: tuple[str, ...]
    fx: FXRate | None


@accounting
def value_portfolio(state: CADState, market: MarketSnapshot, at: datetime, limits: RiskLimits):
    from portfolio_research_desk.domain import require_utc

    require_utc(at)
    if (
        not isinstance(state, CADState)
        or not isinstance(market, MarketSnapshot)
        or not isinstance(limits, RiskLimits)
    ):
        raise DataError("Valuation requires validated CAD state, snapshot and risk limits.")
    if state.as_of > at:
        raise DataError("Cannot value a future state in the past.")
    quotes = market.known_quotes(at, limits)
    sectors = market.known_sectors([p.asset for p in state.positions], at)
    needs_usd = state.balances()["USD"] != 0 or any(
        p.asset.currency == "USD" for p in state.positions
    )
    fx = market.fx.at(at, limits.fx_age) if needs_usd else None
    rate = fx.cad_per_usd if fx else ONE
    cash = state.balances()["CAD"] + state.balances()["USD"] * rate
    rows = []
    for p in state.positions:
        if p.asset not in quotes:
            raise DataError("Missing price for held asset; cannot invent NAV.")
        quote = quotes[p.asset]
        conversion = rate if p.asset.currency == "USD" else ONE
        local_value = p.quantity * quote.price
        rows.append(
            {
                "asset": p.asset,
                "quantity": p.quantity,
                "price_local": quote.price,
                "value_local": local_value,
                "value_cad": local_value * conversion,
                "cost_local": p.cost_local,
                "cost_cad": p.cost_cad,
                "local_pnl": local_value - p.cost_local,
                "cad_pnl": local_value * conversion - p.cost_cad,
                "fx_translation_cad": p.cost_local * conversion - p.cost_cad,
                "local_cost_return": local_value / p.cost_local - ONE if p.cost_local else None,
                "cad_cost_return": local_value * conversion / p.cost_cad - ONE
                if p.cost_cad
                else None,
                "sector": sectors[p.asset],
            }
        )
    nav = cash + sum((p["value_cad"] for p in rows), ZERO)
    exposure = {}
    for p in rows:
        p["weight"] = p["value_cad"] / nav if nav else ZERO
        exposure[p["sector"]] = exposure.get(p["sector"], ZERO) + p["weight"]
    cash_weight = cash / nav if nav else ONE
    violations = []
    if len(rows) > limits.max_positions:
        violations.append("MAX_POSITIONS")
    if any(p["weight"] > limits.max_position_weight for p in rows):
        violations.append("MAX_POSITION_WEIGHT")
    if any(w > limits.max_sector_weight for w in exposure.values()):
        violations.append("MAX_SECTOR_WEIGHT")
    if cash_weight < limits.cash_buffer:
        violations.append("CASH_BUFFER")
    return Valuation(
        at,
        nav,
        cash,
        tuple(rows),
        cash_weight,
        tuple(sorted(exposure.items())),
        tuple(violations),
        fx,
    )


@accounting
def cad_prices(market, at, limits):
    return {
        a: q.price * rate_for(a.currency, market.fx, at, limits.fx_age)
        for a, q in market.known_quotes(at, limits).items()
    }
