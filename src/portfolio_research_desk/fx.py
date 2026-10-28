"""Historical USD/CAD mid rates, with explicit observation and publication times."""

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path

from portfolio_research_desk.domain import BPS, CENT, ONE, require_utc
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.paper_domain import accounting, money, number


@dataclass(frozen=True)
class FXRate:
    observed_at: datetime
    available_at: datetime
    cad_per_usd: Decimal
    source: str
    synthetic: bool

    def __post_init__(self):
        require_utc(self.observed_at)
        require_utc(self.available_at)
        number(self.cad_per_usd, "CAD per USD", Decimal("0.000001"), Decimal("1e6"))
        if (
            self.observed_at > self.available_at
            or not isinstance(self.source, str)
            or not self.source
        ):
            raise DataError("FX requires observation <= availability and a source.")
        if type(self.synthetic) is not bool:
            raise DataError("FX synthetic marker must be explicit.")


@dataclass(frozen=True)
class FXBook:
    rates: tuple[FXRate, ...] = ()

    def __post_init__(self):
        keys = [(r.observed_at, r.available_at) for r in self.rates]
        if len(set(keys)) != len(keys):
            raise DataError("Duplicate/ambiguous FX vintage.")

    def at(self, at: datetime, max_age: timedelta = timedelta(days=7)) -> FXRate:
        require_utc(at)
        if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
            raise DataError("FX max_age must be positive.")
        known = [r for r in self.rates if r.observed_at <= at and r.available_at <= at]
        if not known:
            raise DataError("Missing historical available USD/CAD FX; no future substitution.")
        rate = max(known, key=lambda r: (r.observed_at, r.available_at))
        if at - rate.observed_at > max_age:
            raise DataError("Historical USD/CAD FX is stale.")
        return rate


def load_fx_csv(path: Path) -> FXBook:
    """Native CSV only. Revisions retain their own actual available_at timestamps."""
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != [
                "observed_at",
                "available_at",
                "cad_per_usd",
                "source",
                "synthetic",
            ]:
                raise DataError("Invalid native FX CSV columns.")
            rates = []
            for row in reader:
                if row["synthetic"] not in {"true", "false"}:
                    raise DataError("FX synthetic must be true/false.")
                rates.append(
                    FXRate(
                        datetime.fromisoformat(row["observed_at"]),
                        datetime.fromisoformat(row["available_at"]),
                        Decimal(row["cad_per_usd"]),
                        row["source"],
                        row["synthetic"] == "true",
                    )
                )
            if not rates:
                raise DataError("Empty FX history.")
            return FXBook(tuple(rates))
    except (OSError, ValueError, ArithmeticError, TypeError) as exc:
        raise DataError("Cannot load native FX CSV.") from exc


@accounting
def rate_for(currency, book, at, max_age=timedelta(days=7)):
    if currency == "CAD":
        return ONE
    if currency != "USD":
        raise DataError("Unsupported FX currency.")
    return book.at(at, max_age).cad_per_usd


@dataclass(frozen=True)
class Conversion:
    source_currency: str
    destination_currency: str
    source_amount: Decimal
    destination_amount: Decimal
    fee_cad: Decimal
    rounding_cad: Decimal
    rate: FXRate


@accounting
def fund_usd(amount: Decimal, book: FXBook, at: datetime, fee_bps: Decimal, max_age):
    """Buy exactly the missing USD cents; charge CAD principal and fee once."""
    money(amount, "USD funding", positive=True)
    number(fee_bps, "FX fee bps", maximum=Decimal("9999"))
    rate = book.at(at, max_age)
    exact = amount * rate.cad_per_usd
    principal = exact.quantize(CENT, rounding=ROUND_CEILING)
    fee = (principal * fee_bps / BPS).quantize(CENT, rounding=ROUND_CEILING)
    return Conversion("CAD", "USD", principal, amount, fee, principal - exact, rate)


@accounting
def sell_usd(amount: Decimal, book: FXBook, at: datetime, fee_bps: Decimal, max_age):
    money(amount, "USD conversion", positive=True)
    number(fee_bps, "FX fee bps", maximum=Decimal("9999"))
    rate = book.at(at, max_age)
    exact = amount * rate.cad_per_usd
    principal = exact.quantize(CENT, rounding=ROUND_FLOOR)
    fee = (principal * fee_bps / BPS).quantize(CENT, rounding=ROUND_CEILING)
    if principal <= fee:
        raise DataError("USD conversion proceeds cannot cover fee.")
    return Conversion("USD", "CAD", amount, principal - fee, fee, exact - principal, rate)
