"""Auditable liquidity/momentum/volatility screening using only available observations."""

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Context, Decimal, localcontext

from portfolio_research_desk.data_contracts import History, validate_quality
from portfolio_research_desk.domain import AssetId, UniverseSnapshot, require_utc
from portfolio_research_desk.errors import DataError


@dataclass(frozen=True)
class ScreenRules:
    min_history: int = 21
    momentum_sessions: int = 20
    min_momentum: Decimal | None = None
    volatility_sessions: int = 20
    max_volatility: Decimal | None = None
    liquidity_sessions: int = 20
    min_dollar_volume: Decimal | None = None

    def __post_init__(self) -> None:
        for name in (
            "min_history",
            "momentum_sessions",
            "volatility_sessions",
            "liquidity_sessions",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < (2 if name == "volatility_sessions" else 1):
                raise DataError(f"Invalid positive session window: {name}.")
        for name in ("min_momentum", "max_volatility", "min_dollar_volume"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, Decimal) or not value.is_finite()):
                raise DataError(f"{name} must be a finite decimal.")
        if any(
            value is not None and value < 0
            for value in (self.max_volatility, self.min_dollar_volume)
        ):
            raise DataError("Volatility/liquidity thresholds cannot be negative.")


@dataclass(frozen=True)
class ScreenDecision:
    asset: AssetId
    included: bool
    reasons: tuple[str, ...]
    values: dict
    value_as_of: date | None
    available_at: datetime | None


@dataclass(frozen=True)
class ScreeningResult:
    universe: UniverseSnapshot
    decisions: tuple[ScreenDecision, ...]
    annualization_sessions: int = 252


def screen_universe(
    snapshot: UniverseSnapshot,
    histories: dict[AssetId, History],
    rules: ScreenRules,
    decision_at: datetime,
    expected_sessions: tuple[date, ...] | None = None,
) -> ScreeningResult:
    require_utc(decision_at)
    decisions = []
    selected = []
    with localcontext(Context(prec=28)):
        for asset in snapshot.assets:
            reasons, values = [], {}
            source = histories.get(asset)
            if (
                snapshot.available_at is None
                or snapshot.available_at > decision_at
                or snapshot.as_of > decision_at
            ):
                reasons.append("UNIVERSE_UNAVAILABLE")
            if source is None:
                reasons.append("DATA_UNAVAILABLE")
                past = ()
            else:
                if (
                    snapshot.synthetic is None
                    or (source.data_kind == "synthetic") != snapshot.synthetic
                ):
                    raise DataError("Universe and history real/synthetic kinds do not match.")
                past = tuple(
                    sorted(
                        (
                            r
                            for r in source.rows
                            if r.asset == asset and r.observation_end <= decision_at
                        ),
                        key=lambda r: r.session_date,
                    )
                )
                if any(r.available_at > decision_at for r in past):
                    reasons.append("INPUT_UNAVAILABLE")
                if past:
                    calendar = (
                        tuple(d for d in expected_sessions if d <= decision_at.date())
                        if expected_sessions
                        else None
                    )
                    quality = validate_quality(replace(source, rows=past), calendar)
                    errors = sorted(
                        {issue.code for issue in quality.issues if issue.severity == "ERROR"}
                    )
                    reasons.extend(f"QUALITY_{code}" for code in errors)
            required = max(
                rules.min_history,
                rules.momentum_sessions + 1,
                rules.volatility_sessions + 1,
                rules.liquidity_sessions,
            )
            if len(past) < required:
                reasons.append("INSUFFICIENT_HISTORY")
            if not reasons:
                window = past[-required:]
                if any(r.dividend != 0 or r.split_ratio not in {0, 1} for r in window):
                    reasons.append("CORPORATE_ACTION_REVIEW_REQUIRED")
                if past[-1].volume == 0:
                    reasons.append("NO_RECENT_VOLUME")
            if not reasons:
                momentum = past[-1].close / past[-rules.momentum_sessions - 1].close - 1
                vol_rows = past[-rules.volatility_sessions - 1 :]
                returns = [
                    current.close / previous.close - 1
                    for previous, current in zip(vol_rows[:-1], vol_rows[1:], strict=True)
                ]
                mean = sum(returns) / len(returns)
                variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
                volatility = variance.sqrt() * Decimal(252).sqrt()
                liquidity = (
                    sum(r.close * r.volume for r in past[-rules.liquidity_sessions :])
                    / rules.liquidity_sessions
                )
                values = {
                    "history_sessions": len(past),
                    "momentum": str(momentum),
                    "annualized_sample_volatility": str(volatility),
                    "avg_close_times_volume_USD": str(liquidity),
                    "price_basis": source.price_basis,
                }
                if rules.min_momentum is not None and momentum < rules.min_momentum:
                    reasons.append("MOMENTUM_BELOW_MIN")
                if rules.max_volatility is not None and volatility > rules.max_volatility:
                    reasons.append("VOLATILITY_ABOVE_MAX")
                if rules.min_dollar_volume is not None and liquidity < rules.min_dollar_volume:
                    reasons.append("LIQUIDITY_BELOW_MIN")
            if not reasons:
                selected.append(asset)
            decisions.append(
                ScreenDecision(
                    asset,
                    not reasons,
                    tuple(reasons) or ("PASSED",),
                    values,
                    past[-1].session_date if past else None,
                    max(r.available_at for r in past) if past else None,
                )
            )
    screened = replace(snapshot, assets=tuple(selected), screening_applied=True)
    return ScreeningResult(screened, tuple(decisions))
