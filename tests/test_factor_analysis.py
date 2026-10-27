import math
from dataclasses import replace

import numpy as np
import pytest
from scipy.stats import t as student_t

from portfolio_research_desk.errors import DataError
from portfolio_research_desk.factor_analysis import compare_models, fit_ols, rolling_exposures
from portfolio_research_desk.factor_config import load_factor_config
from portfolio_research_desk.factor_returns import AlignedSample
from portfolio_research_desk.factor_workflow import run_factor_research


@pytest.fixture(scope="module")
def research():
    return run_factor_research(load_factor_config())


def test_orthogonal_known_coefficients_se_t_p_ci_r2_aic_bic(research):
    sample = research.sample
    fit = fit_ols(sample, covariance="nonrobust")
    n, p = 96, 5
    assert fit["nobs"] == n
    expected = {"Alpha": 0.0002, "Mkt-RF": 0.8, "SMB": 0.3, "HML": -0.2, "Mom": 0.5}
    residual_variance = n * 0.0003**2 / (n - p)
    ssx = dict(
        zip(expected, [n, n * 0.01**2, n * 0.006**2, n * 0.008**2, n * 0.012**2], strict=True)
    )
    for name, beta in expected.items():
        result = fit["coefficients"][name]
        se = math.sqrt(residual_variance / ssx[name])
        statistic = beta / se
        assert result["estimate"] == pytest.approx(beta, abs=1e-12)
        assert result["std_error"] == pytest.approx(se, rel=1e-10)
        assert result["t_statistic"] == pytest.approx(statistic)
        assert result["p_value"] == pytest.approx(2 * student_t.sf(abs(statistic), n - p))
        assert result["ci_lower"] == pytest.approx(beta - student_t.ppf(0.975, n - p) * se)
        assert result["ci_upper"] == pytest.approx(beta + student_t.ppf(0.975, n - p) * se)
    signal_var = (0.8 * 0.01) ** 2 + (0.3 * 0.006) ** 2 + (-0.2 * 0.008) ** 2 + (0.5 * 0.012) ** 2
    r2 = signal_var / (signal_var + 0.0003**2)
    assert fit["r_squared"] == pytest.approx(r2)
    assert fit["adjusted_r_squared"] == pytest.approx(1 - (1 - r2) * (n - 1) / (n - p))
    neg2ll = n * (math.log(2 * math.pi) + 1 + math.log(0.0003**2))
    assert fit["aic"] == pytest.approx(neg2ll + 2 * p)
    assert fit["bic"] == pytest.approx(neg2ll + math.log(n) * p)
    assert max(abs(np.array(fit["residuals"]))) == pytest.approx(0.0003)


def test_hc3_has_independently_known_covariance_on_equal_leverage_design(research):
    classical = fit_ols(research.sample, covariance="nonrobust")
    robust = fit_ols(research.sample, covariance="HC3")
    for name in classical["coefficients"]:
        assert robust["coefficients"][name]["std_error"] == pytest.approx(
            classical["coefficients"][name]["std_error"] * math.sqrt(96 / 91)
        )
    assert robust["aic"] == classical["aic"]
    assert robust["diagnostics"]["max_leverage"] == pytest.approx(5 / 96)


def test_same_sample_ff3_ff4_comparison_and_omitted_orthogonal_momentum(research):
    comparison = compare_models(research.sample)
    a, b = comparison["fits"].values()
    assert a["sample_hash"] == b["sample_hash"] == research.sample.sample_hash
    assert a["nobs"] == b["nobs"] == 96
    for key in ("Alpha", "Mkt-RF", "SMB", "HML"):
        assert a["coefficients"][key]["estimate"] == pytest.approx(
            b["coefficients"][key]["estimate"]
        )
    assert comparison["delta_aic_FF4_minus_FF3"] < 0


def test_rolling_known_coefficients_and_future_perturbation(research):
    original = rolling_exposures(research.sample, window=32)
    assert len(original) == 65
    for row in original:
        assert row["nobs"] == 32 and row["status"] == "complete"
        assert row["comparison"]["fits"]["FF4"]["coefficients"]["Mom"]["estimate"] == pytest.approx(
            0.5
        )
        assert row["comparison"]["fits"]["FF4"]["coefficients"]["Alpha"][
            "estimate"
        ] == pytest.approx(0.0002)
        assert not row["historical_signal_eligible"]
    boundary = research.sample.rows[63].period
    changed = replace(
        research.sample,
        rows=tuple(
            replace(r, excess_return=r.excess_return * 20, factors=tuple(v * 7 for v in r.factors))
            if r.period > boundary
            else r
            for r in research.sample.rows
        ),
    )
    modified = rolling_exposures(changed, window=32)
    assert [r for r in original if r["window_end"] <= str(boundary)] == [
        r for r in modified if r["window_end"] <= str(boundary)
    ]


def test_rolling_missing_period_does_not_expand_window_to_older_rows(research):
    missing = research.sample.rows[15].period
    sample = replace(
        research.sample,
        rows=tuple(r for r in research.sample.rows if r.period != missing),
        exclusions=({"period": str(missing), "reason": "MISSING"},),
    )
    rolling = rolling_exposures(sample, window=32)
    assert len(rolling) == 65
    assert rolling[0]["nobs"] == 31
    assert rolling[0]["window_start"] == str(research.sample.rows[0].period)
    failed = rolling_exposures(sample, window=32, min_obs=32)
    assert failed[0]["status"] == "failed" and "INSUFFICIENT_SAMPLE" in failed[0]["reason"]


@pytest.mark.parametrize(
    "change,reason",
    [
        ("short", "INSUFFICIENT_SAMPLE"),
        ("singular", "SINGULAR_DESIGN"),
        ("constant", "CONSTANT_RESPONSE"),
        ("nan", "NONFINITE"),
        ("duplicate", "unique"),
    ],
)
def test_invalid_regressions_fail_explicitly(research, change, reason):
    rows = research.sample.rows
    if change == "short":
        rows = rows[:5]
    if change == "singular":
        rows = tuple(replace(r, factors=(r.factors[0],) * 4) for r in rows)
    if change == "constant":
        rows = tuple(replace(r, excess_return=0.1) for r in rows)
    if change == "nan":
        rows = (replace(rows[0], excess_return=float("nan")), *rows[1:])
    if change == "duplicate":
        rows = (rows[0], *rows)
    with pytest.raises(DataError, match=reason):
        fit_ols(AlignedSample("daily", rows, ()))


def test_perfect_fit_reports_estimates_without_spurious_inference(research):
    rows = tuple(
        replace(
            r,
            excess_return=0.001
            + sum(a * b for a, b in zip(r.factors, [1.0, 0.2, -0.3, 0.4], strict=True)),
        )
        for r in research.sample.rows
    )
    fit = fit_ols(replace(research.sample, rows=rows))
    assert fit["coefficients"]["Alpha"]["estimate"] == pytest.approx(0.001)
    assert fit["coefficients"]["Alpha"]["p_value"] is None
    assert fit["aic"] is None and any("PERFECT_FIT" in w for w in fit["warnings"])


def test_near_collinear_factors_warn_before_severe_rank_failure(research):
    rows = tuple(
        replace(
            r,
            factors=(r.factors[0], r.factors[1], r.factors[2], r.factors[0] + 0.01 * r.factors[3]),
        )
        for r in research.sample.rows
    )
    fit = fit_ols(replace(research.sample, rows=rows))
    assert any("MULTICOLLINEARITY" in w for w in fit["warnings"])
