"""Endpoint holding-period returns and exact-date common-sample alignment."""

import calendar
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Context, Decimal, localcontext

from portfolio_research_desk.data_contracts import History, validate_quality
from portfolio_research_desk.domain import AssetId, fingerprint, require_utc
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.factor_data import FactorData


@dataclass(frozen=True)
class ReturnRow:
    period: date
    start: date
    value: Decimal
    available_at: datetime

    def __post_init__(self):
        require_utc(self.available_at)
        if self.start >= self.period or not self.value.is_finite() or self.value < -1:
            raise DataError("Invalid holding-period return or interval.")


@dataclass(frozen=True)
class ReturnData:
    asset: AssetId
    frequency: str
    rows: tuple[ReturnRow, ...]
    basis: str
    history_hash: str
    warnings: tuple[str, ...]

    def __post_init__(self):
        dates = [r.period for r in self.rows]
        if self.frequency not in {"daily", "monthly"} or dates != sorted(set(dates)):
            raise DataError("Return dates must be ordered, unique and explicitly daily/monthly.")
        if self.asset.market != "US" or self.asset.currency != "USD":
            raise DataError("US French regressions require US/USD returns; FX is unavailable.")
        if self.frequency == "monthly" and any(_month_end(d) != d for d in dates):
            raise DataError("Monthly returns require calendar month-end labels.")


def _month_end(day):
    return date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])


def monthly_period_grid(start: date, end: date) -> tuple[date, ...]:
    """All calendar month-end labels inside inclusive bounds, including absent months."""
    first = start.year * 12 + start.month - 1
    last = end.year * 12 + end.month - 1
    periods = (_month_end(date(index // 12, index % 12 + 1, 1)) for index in range(first, last + 1))
    return tuple(period for period in periods if start <= period <= end)


def calculate_returns(
    history: History,
    factors: FactorData,
    basis="adjusted_close",
    sessions: tuple[date, ...] | None = None,
) -> ReturnData:
    with localcontext(Context(prec=28)):
        return _calculate_returns(history, factors, basis, sessions)


def _calculate_returns(history, factors, basis, sessions):
    """Daily adjacent French dates, or declared monthly session endpoints; never bridge gaps.

    Adjusted-close ratios are a provider total-return proxy, not an independently
    certified dividend-reinvestment ledger. Plain close rejects declared adjusted
    input and action intervals; provider OHLC retains its adjustment uncertainty.
    Neither series is an execution price.
    """
    assets = {r.asset for r in history.rows}
    if len(assets) != 1:
        raise DataError("Factor research takes one explicitly identified asset per history.")
    if (history.data_kind == "synthetic") != factors.synthetic:
        raise DataError("Real and synthetic factor/price inputs cannot be mixed.")
    if basis not in {"close", "adjusted_close"}:
        raise DataError("Return basis must be close or adjusted_close.")
    if basis == "close" and history.price_basis == "provider_adjusted":
        raise DataError(
            "PRICE_BASIS_CONFLICT: provider_adjusted Close cannot be labelled price-only. "
            "Use a declared unadjusted series or an explicit adjusted_close return proxy."
        )
    quality = validate_quality(history)
    for issue in quality.issues:
        if issue.code == "SESSION_TIME_MISMATCH":
            raise DataError(f"{issue.code}: {issue.session_date}: {issue.message}")
    prices = {r.session_date: r for r in quality.accepted}
    if not prices:
        raise DataError("No quality-accepted prices for factor returns.")
    warnings = [
        "Descriptive USD returns; no execution, PIT or survivorship-bias certification.",
        "Adjusted-close ratio is a provider total-return proxy; no dividends added again."
        if basis == "adjusted_close"
        else "Close-column return proxy: cash dividends are not added; "
        "provider OHLC adjustment conventions remain unverified."
        if history.price_basis == "provider_ohlc"
        else "Declared unadjusted Close PRICE returns excluding dividends; "
        "alpha is not total-return alpha.",
    ]
    warnings.extend(
        sorted(
            {
                f"{i.code}: {i.message}"
                for i in quality.issues
                if i.code == "SESSION_TIME_UNVERIFIED"
            }
        )
    )
    if quality.quarantined:
        warnings.append(
            f"Quarantined {len(quality.quarantined)} price observations; no gap filling."
        )
    if factors.frequency == "daily":
        # Union preserves observed price dates even when a factor date is absent;
        # otherwise a missing factor Tuesday could turn Wednesday into a two-day return.
        calendar_dates = sorted(
            {r.period for r in factors.rows} | {r.session_date for r in history.rows}
        )
        endpoints = [
            (d, p, d) for p, d in zip(calendar_dates[:-1], calendar_dates[1:], strict=True)
        ]
        warnings.append(
            "Daily intervals use adjacent French factor dates; exchange calendar unverified."
        )
    else:
        if (
            not sessions
            or any(type(day) is not date for day in sessions)
            or list(sessions) != sorted(set(sessions))
        ):
            raise DataError(
                "Monthly returns require an ordered, unique declared daily session calendar."
            )
        session_dates = set(sessions)
        first_month, last_month = _month_end(sessions[0]), _month_end(sessions[-1])
        conflicts = sorted(
            {
                row.session_date
                for row in history.rows
                if first_month <= _month_end(row.session_date) <= last_month
                and row.session_date not in session_dates
            }
        )
        if conflicts:
            raise DataError(
                "CALENDAR_PRICE_CONFLICT: observed price date is absent from the declared "
                f"session calendar: {conflicts[0]}. Refusing ambiguous monthly endpoints."
            )
        by_month = {}
        for day in sessions:
            by_month[_month_end(day)] = day
        endpoints = []
        months = sorted(by_month)
        for previous, current in zip(months[:-1], months[1:], strict=True):
            if current.year * 12 + current.month - previous.year * 12 - previous.month == 1:
                endpoints.append((current, by_month[previous], by_month[current]))
        warnings.append(
            "Monthly endpoints use the supplied session calendar; its authority is user-declared."
        )
    result = []
    for period, previous, current in endpoints:
        if previous not in prices or current not in prices:
            continue
        left, right = prices[previous], prices[current]
        interval = [r for r in history.rows if previous < r.session_date <= current]
        if basis == "close" and any(r.dividend or r.split_ratio not in {0, 1} for r in interval):
            warnings.append(f"CORPORATE_ACTION: excluded return {period} on plain close basis.")
            continue
        first = left.adj_close if basis == "adjusted_close" else left.close
        last = right.adj_close if basis == "adjusted_close" else right.close
        if first is None or last is None or first <= 0 or last <= 0:
            continue
        result.append(
            ReturnRow(
                period,
                previous,
                last / first - 1,
                max(left.available_at, right.available_at, history.retrieved_at),
            )
        )
    return ReturnData(
        next(iter(assets)),
        factors.frequency,
        tuple(result),
        basis,
        history.snapshot_hash,
        tuple(dict.fromkeys(warnings)),
    )


@dataclass(frozen=True)
class AlignedRow:
    period: date
    start: date
    stock_return: float
    rf: float
    excess_return: float
    factors: tuple[float, float, float, float]
    available_at: datetime


@dataclass(frozen=True)
class AlignedSample:
    frequency: str
    rows: tuple[AlignedRow, ...]
    exclusions: tuple[dict, ...]

    @property
    def sample_hash(self):
        return fingerprint(self.rows)


def align_common_sample(
    returns: ReturnData, factors: FactorData, start: date, end: date
) -> AlignedSample:
    with localcontext(Context(prec=28)):
        return _align_common_sample(returns, factors, start, end)


def _align_common_sample(returns, factors, start, end):
    """Inner alignment without filling; FF3 and FF4 BOTH use complete four-factor rows."""
    if returns.frequency != factors.frequency:
        raise DataError("Return/factor frequency mismatch; no implicit resampling.")
    if start >= end:
        raise DataError("Expected start < exclusive end.")
    stock = {r.period: r for r in returns.rows}
    factor = {r.period: r for r in factors.rows}
    periods = sorted(stock.keys() | factor.keys())
    previous_period = dict(zip(periods[1:], periods[:-1], strict=True))
    rows, excluded = [], []
    candidates = monthly_period_grid(start, end) if factors.frequency == "monthly" else periods
    for period in candidates:
        if not start <= period < end:
            continue
        r, f = stock.get(period), factor.get(period)
        reason = (
            "MISSING_STOCK_AND_FACTOR"
            if r is None and f is None
            else "MISSING_STOCK_RETURN"
            if r is None
            else "MISSING_FACTOR_DATE"
            if f is None
            else None
        )
        if f and any(v is None for v in (f.mkt_rf, f.smb, f.hml, f.rf, f.mom)):
            reason = "MISSING_FACTOR_VALUE"
        if r and f:
            if (
                factors.frequency == "daily"
                and period in previous_period
                and r.start != previous_period[period]
            ):
                reason = "RETURN_INTERVAL_MISMATCH"
            if factors.frequency == "monthly" and (
                period.year * 12 + period.month - r.start.year * 12 - r.start.month != 1
            ):
                reason = "RETURN_INTERVAL_MISMATCH"
        if reason:
            excluded.append({"period": period.isoformat(), "reason": reason})
            continue
        values = tuple(float(v) for v in (f.mkt_rf, f.smb, f.hml, f.mom))
        rows.append(
            AlignedRow(
                period,
                r.start,
                float(r.value),
                float(f.rf),
                float(r.value - f.rf),
                values,
                max(r.available_at, factors.retrieved_at),
            )
        )
    return AlignedSample(factors.frequency, tuple(rows), tuple(excluded))
