"""OLS diagnostics and trailing-period exposures; no signals, fitting pipeline or OOS claims."""

import math
import warnings
from datetime import date

from portfolio_research_desk.domain import fingerprint
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.factor_data import FACTOR_NAMES
from portfolio_research_desk.factor_returns import AlignedSample, monthly_period_grid


def _libraries():
    try:
        import numpy as np
        from statsmodels.regression.linear_model import OLS
        from statsmodels.stats.diagnostic import het_breuschpagan
        from statsmodels.stats.stattools import durbin_watson, jarque_bera
    except ImportError as exc:
        raise DataError("Install the locked factors extra for regression and charts.") from exc
    return np, OLS, het_breuschpagan, durbin_watson, jarque_bera


def _finite(value):
    value = float(value)
    return value if math.isfinite(value) else None


def require_factor_dependencies():
    """Missing optional installation is an input error, not a failed statistical fit."""
    _libraries()
    try:
        import matplotlib

        _ = matplotlib.__version__
    except ImportError as exc:
        raise DataError("Install the locked factors extra for regression and charts.") from exc


def fit_ols(
    sample: AlignedSample, model="FF4", covariance="HC3", min_obs=20, confidence=0.95
) -> dict:
    np, OLS, bp, dw, jb = _libraries()
    if model not in {"FF3", "FF4"} or covariance not in {"nonrobust", "HC3"}:
        raise DataError("Expected FF3/FF4 and nonrobust/HC3 covariance.")
    if type(min_obs) is not int or min_obs < 6 or not 0 < confidence < 1:
        raise DataError("min_obs must be >=6 and confidence must be in (0,1).")
    count = 3 if model == "FF3" else 4
    n = len(sample.rows)
    if n < min_obs or n <= count + 1:
        raise DataError(f"INSUFFICIENT_SAMPLE: {n} rows; need >= {max(min_obs, count + 2)}.")
    dates = [r.period for r in sample.rows]
    if dates != sorted(set(dates)):
        raise DataError("Regression observations must have unique ordered dates.")
    x = np.array([r.factors[:count] for r in sample.rows], dtype=float)
    y = np.array([r.excess_return for r in sample.rows], dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise DataError("NONFINITE_REGRESSION_INPUT: no implicit missing-data removal.")
    scales = x.std(axis=0)
    if np.any(scales <= np.finfo(float).eps):
        raise DataError("SINGULAR_DESIGN: constant factor column.")
    standardized = (x - x.mean(axis=0)) / scales
    design = np.column_stack((np.ones(n), x))
    scaled_design = np.column_stack((np.ones(n), standardized))
    condition = float(np.linalg.cond(scaled_design))
    if np.linalg.matrix_rank(scaled_design) < count + 1 or condition > 1e8:
        raise DataError("SINGULAR_DESIGN: rank deficient or severely ill-conditioned factors.")
    if np.ptp(y) <= np.finfo(float).eps * max(1.0, float(np.abs(y).max())):
        raise DataError("CONSTANT_RESPONSE: R-squared and attribution are not informative.")
    alerts = []
    # Auxiliary regressions avoid squaring the design condition number in X'X.
    vif = []
    for column in range(count):
        others = np.delete(standardized, column, axis=1)
        fitted = others @ np.linalg.lstsq(others, standardized[:, column], rcond=None)[0]
        residual_ss = float(np.sum((standardized[:, column] - fitted) ** 2))
        vif.append(n / residual_ss)
    if condition > 30 or max(vif) > 10:
        alerts.append("MULTICOLLINEARITY: elevated scaled condition number or VIF > 10.")
    if n < max(30, 5 * (count + 1)):
        alerts.append(
            "SMALL_SAMPLE: inference is fragile even though residual degrees of freedom exist."
        )
    if sample.exclusions:
        alerts.append(
            "COMPLETE_CASE: exclusions can cause selection bias and irregular residual spacing."
        )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            result = OLS(y, design, missing="raise", hasconst=True).fit(
                cov_type=covariance, use_t=True
            )
        except (ValueError, np.linalg.LinAlgError, FloatingPointError) as exc:
            raise DataError("REGRESSION_FAILURE: OLS could not fit this design.") from exc
        residuals = result.resid
        perfect = np.linalg.norm(residuals) <= 100 * np.finfo(float).eps * np.linalg.norm(y)
        if perfect:
            alerts.append(
                "PERFECT_FIT: residual variance is numerically zero; inference/AIC/BIC unavailable."
            )
        intervals = result.conf_int(alpha=1 - confidence)
        names = ("Alpha", *FACTOR_NAMES[:count])
        coefficients = {}
        for i, name in enumerate(names):
            coefficients[name] = {
                "estimate": _finite(result.params[i]),
                "std_error": None if perfect else _finite(result.bse[i]),
                "t_statistic": None if perfect else _finite(result.tvalues[i]),
                "p_value": None if perfect else _finite(result.pvalues[i]),
                "ci_lower": None if perfect else _finite(intervals[i, 0]),
                "ci_upper": None if perfect else _finite(intervals[i, 1]),
            }
        leverage = np.sum(design * np.linalg.pinv(design).T, axis=1)
        diagnostics = {
            "rank": count + 1,
            "condition_number_scaled": condition,
            "condition_number_raw": _finite(np.linalg.cond(design)),
            "vif": {name: _finite(value) for name, value in zip(names[1:], vif, strict=True)},
            "max_leverage": _finite(max(leverage)),
            "residual_mean": _finite(np.mean(residuals)),
            "residual_std": None if perfect else _finite(np.sqrt(result.ssr / result.df_resid)),
            "durbin_watson": None if perfect else _finite(dw(residuals)),
            "breusch_pagan_lm_pvalue": None if perfect else _finite(bp(residuals, design)[1]),
            "jarque_bera_pvalue": None if perfect or n < 8 else _finite(jb(residuals)[1]),
        }
        for item in caught:
            alerts.append(f"NUMERICAL_WARNING: {item.category.__name__}: {item.message}")
    if any(c["estimate"] is None for c in coefficients.values()):
        raise DataError("REGRESSION_FAILURE: nonfinite coefficient.")
    if not perfect and any(c["std_error"] is None for c in coefficients.values()):
        alerts.append("INFERENCE_UNAVAILABLE: covariance calculation produced nonfinite results.")
    if covariance == "nonrobust":
        alerts.append("CLASSICAL_SE: assumes homoskedastic, uncorrelated errors for inference.")
    else:
        alerts.append(
            "HC3_SE: heteroskedasticity robust; no serial-correlation correction; "
            "t inference is approximate."
        )
    return {
        "model": model,
        "status": "complete",
        "frequency": sample.frequency,
        "response": "stock_simple_return_minus_RF",
        "alpha_unit": "decimal_per_period",
        "nobs": n,
        "df_model": count,
        "df_resid": int(result.df_resid),
        "sample_start": dates[0].isoformat(),
        "sample_end": dates[-1].isoformat(),
        "sample_hash": sample.sample_hash,
        "covariance": covariance,
        "confidence": confidence,
        "coefficients": coefficients,
        "r_squared": _finite(result.rsquared),
        "adjusted_r_squared": _finite(result.rsquared_adj),
        "aic": None if perfect else _finite(result.aic),
        "bic": None if perfect else _finite(result.bic),
        "log_likelihood": None if perfect else _finite(result.llf),
        "diagnostics": diagnostics,
        "warnings": alerts,
        "fitted": [float(v) for v in result.fittedvalues],
        "residuals": [float(v) for v in residuals],
    }


def compare_models(sample: AlignedSample, **options) -> dict:
    """Same response, dates, four-factor complete cases and Gaussian OLS likelihood."""
    fits = {model: fit_ols(sample, model, **options) for model in ("FF3", "FF4")}
    return {
        "fits": fits,
        "common_sample_hash": sample.sample_hash,
        "delta_aic_FF4_minus_FF3": None
        if any(v["aic"] is None for v in fits.values())
        else fits["FF4"]["aic"] - fits["FF3"]["aic"],
        "delta_bic_FF4_minus_FF3": None
        if any(v["bic"] is None for v in fits.values())
        else fits["FF4"]["bic"] - fits["FF3"]["bic"],
    }


def rolling_exposures(sample: AlignedSample, window=60, **options) -> tuple[dict, ...]:
    """Trailing N nominal factor periods, then complete cases INSIDE that window.

    Missing observations never pull in older data to enlarge the window. A failed
    window is retained with its reason; no centered windows or global fitting.
    """
    if type(window) is not int or window < 6:
        raise DataError("Rolling window must be an integer >=6 periods.")
    periods = sorted(
        {r.period for r in sample.rows}
        | {date.fromisoformat(r["period"]) for r in sample.exclusions}
    )
    if sample.frequency == "monthly" and periods:
        periods = monthly_period_grid(periods[0], periods[-1])
    output = []
    for index in range(window - 1, len(periods)):
        left, right = periods[index - window + 1], periods[index]
        rows = tuple(r for r in sample.rows if left <= r.period <= right)
        subset = AlignedSample(
            sample.frequency,
            rows,
            tuple(
                e for e in sample.exclusions if left.isoformat() <= e["period"] <= right.isoformat()
            ),
        )
        record = {
            "window_start": left.isoformat(),
            "window_end": right.isoformat(),
            "window_periods": window,
            "nobs": len(rows),
            "available_at": max((r.available_at for r in rows), default=None),
            "historical_signal_eligible": False,
        }
        try:
            comparison = compare_models(subset, **options)
            record.update(status="complete", comparison=comparison)
        except DataError as exc:
            record.update(status="failed", reason=str(exc))
        record["window_hash"] = fingerprint(subset)
        output.append(record)
    return tuple(output)
