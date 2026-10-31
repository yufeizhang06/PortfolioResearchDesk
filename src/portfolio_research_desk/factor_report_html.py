"""Human-readable factor attribution from existing serialized results only."""

from portfolio_research_desk.report_design import (
    bullets,
    document,
    downloads,
    e,
    line_chart,
    metric,
    notice,
    number,
    percent,
    pvalue,
    section,
    stamp,
    table,
    time_range,
)

TERMS = ("Alpha", "Mkt-RF", "SMB", "HML", "Mom")


def render_factor_report(data, run_id, generated_at):
    config, sample = data["config"], data["alignment"]
    comparison, rolling = data["analysis"], data["rolling"]
    fits = comparison["fits"] if comparison else {}
    ff4 = fits.get("FF4", {})
    coefficients = ff4.get("coefficients", {})
    frequency = "day" if config["frequency"] == "daily" else "month"
    rows = sample["rows"]
    dates = [str(row["period"]) for row in rows]
    interval = f"{min(dates)} to {max(dates)}" if dates else "No aligned observations"
    badges = (
        "SYNTHETIC" if config["expected_kind"] == "synthetic" else "OBSERVED INPUTS",
        "USD",
        "EX-POST DESCRIPTIVE",
    )
    overview = notice(
        "Ex-post descriptive research. These fits explain this sample; they are not forecasts, "
        "historical trading signals, or real-market OOS profitability evidence.",
        True,
    )
    if not comparison:
        overview += notice(
            "Analysis failed: insufficient or unsuitable common observations. "
            "No fitted coefficients or successful diagnostics are shown."
        )
    overview += (
        '<div class="metrics">'
        + "".join(
            (
                metric(
                    "FF4 Alpha",
                    percent(coefficients.get("Alpha", {}).get("estimate"), 4),
                    f"Excess-return intercept per {frequency}",
                    "factor-alpha",
                    True,
                ),
                metric(
                    "FF4 Market Beta",
                    number(coefficients.get("Mkt-RF", {}).get("estimate"), 3),
                    "Exposure to market excess return",
                    "factor-beta",
                ),
                metric(
                    "FF4 R-squared",
                    percent(ff4.get("r_squared")),
                    "In-sample variation explained",
                    "factor-r2",
                ),
                metric(
                    "Common observations",
                    f"{len(rows):,}",
                    "Identical rows for FF3 and FF4",
                    "factor-nobs",
                ),
            )
        )
        + "</div>"
    )
    overview += '<p class="section-intro">Alpha is the fitted intercept after factor attribution. '
    overview += (
        "Beta measures sensitivity to a factor, not the probability of profit. "
        "A high R-squared measures sample fit, not predictive skill.</p>"
    )
    model_rows = [
        [
            e(model),
            percent(fit.get("r_squared")),
            percent(fit.get("adjusted_r_squared")),
            number(fit.get("aic")),
            number(fit.get("bic")),
            str(fit.get("nobs", "-")),
        ]
        for model, fit in fits.items()
    ]
    overview += section(
        "FF3 / FF4 comparison",
        table(
            ("Model", "R-squared", "Adjusted R²", "AIC", "BIC", "Observations"),
            model_rows,
            "factor-comparison",
            (1, 2, 3, 4, 5),
        ),
        "comparison",
    )
    if comparison:
        overview += '<p class="note">FF4 adds momentum to FF3. Lower AIC/BIC means a better '
        overview += (
            "penalized fit on this identical sample. FF4 minus FF3: AIC "
            f"{number(comparison['delta_aic_FF4_minus_FF3'])}; BIC "
            f"{number(comparison['delta_bic_FF4_minus_FF3'])}. "
            "This comparison does not select a trading strategy.</p>"
        )
    overview += "<h2>Rolling Exposure</h2>"
    overview += line_chart(
        [row["window_end"] for row in rolling],
        [
            (
                term,
                [
                    row["comparison"]["fits"]["FF4"]["coefficients"][term]["estimate"]
                    if row["status"] == "complete"
                    else None
                    for row in rolling
                ],
            )
            for term in TERMS[1:]
        ],
        "factor-rolling",
        "Trailing FF4 factor betas",
        lambda v: number(v, 2),
        note=f"Trailing {config['rolling_window']} {config['frequency']} observations; "
        "dimensionless betas. Failed windows are gaps, never interpolated.",
    )
    overview += f'<p class="note">{len(rolling):,} recorded windows; '
    overview += (
        f"{sum(row['status'] != 'complete' for row in rolling):,} failed. "
        "Every window and failure reason remains in rolling.csv.</p>"
    )

    coefficient_rows = []
    for model, fit in fits.items():
        for term in TERMS:
            row = fit["coefficients"].get(term)
            if row is None:
                continue
            fmt = (lambda v: percent(v, 4)) if term == "Alpha" else (lambda v: number(v, 3))
            coefficient_rows.append(
                [
                    e(model),
                    e(term),
                    fmt(row["estimate"]),
                    fmt(row["std_error"]),
                    number(row["t_statistic"], 2),
                    e(pvalue(row["p_value"])),
                    f"{fmt(row['ci_lower'])} to {fmt(row['ci_upper'])}",
                ]
            )
    details = table(
        (
            "Model",
            "Term",
            "Estimate",
            "Std. error",
            "t statistic",
            "p value",
            f"{percent(config['confidence'], 0)} interval",
        ),
        coefficient_rows,
        "factor-coefficients",
        (2, 3, 4, 5, 6),
    )
    details += '<p class="note">Alpha and its interval/standard error are percent per '
    details += (
        f"{frequency}; betas are dimensionless. An interval excluding zero indicates "
        f"evidence against a zero coefficient under the fitted {e(config['covariance'])} "
        "assumptions. It is not proof of persistent alpha; multiple tests and serial "
        "dependence matter. Small p values are shown as &lt;0.0001, not rounded to zero.</p>"
    )
    diagnostic_spec = (
        (
            "Durbin-Watson",
            "durbin_watson",
            "Near 2 suggests less first-order residual autocorrelation.",
            number,
        ),
        (
            "Residual normality p",
            "jarque_bera_pvalue",
            "Small p challenges a normal-residual assumption.",
            pvalue,
        ),
        (
            "Heteroskedasticity p",
            "breusch_pagan_lm_pvalue",
            "Small p suggests nonconstant residual variance.",
            pvalue,
        ),
        (
            "Scaled condition number",
            "condition_number_scaled",
            "Large values indicate unstable, collinear inputs.",
            number,
        ),
        (
            "Maximum leverage",
            "max_leverage",
            "Influence potential of the most unusual design row.",
            number,
        ),
    )
    diagnostic_rows = [
        [label]
        + [e(fmt(fits.get(model, {}).get("diagnostics", {}).get(key))) for model in ("FF3", "FF4")]
        + [explanation]
        for label, key, explanation, fmt in diagnostic_spec
    ]
    details += "<h2>Diagnostics</h2>" + table(
        ("Diagnostic", "FF3", "FF4", "How to read it"),
        diagnostic_rows,
        "factor-diagnostics",
        (1, 2),
    )
    vif = [
        [term]
        + [
            number(fits.get(model, {}).get("diagnostics", {}).get("vif", {}).get(term), 3)
            for model in ("FF3", "FF4")
        ]
        for term in TERMS[1:]
    ]
    details += "<h3>Variance inflation factors</h3>" + table(
        ("Factor", "FF3 VIF", "FF4 VIF"), vif, "factor-vif", (1, 2)
    )
    details += '<p class="note">VIF describes overlap between explanatory factors. '
    details += "Momentum is absent from FF3, so its FF3 VIF is unavailable.</p>"

    factors, history = data["factor_snapshot"], data["price_snapshot"]
    quality = data["quality"].get("prices", {})
    methodology = table(
        ("Item", "Recorded source / interpretation"),
        [
            [
                "Asset",
                e(
                    " / ".join(
                        data["returns"]["asset"][k] for k in ("symbol", "exchange", "currency")
                    )
                ),
            ],
            ["Price provider / basis", e(f"{history['provider']} / {data['returns']['basis']}")],
            ["Factor source", e(factors["source"])],
            ["Factor snapshot retrieved", e(stamp(factors["retrieved_at"]))],
            ["Factor availability basis", e(factors["availability_basis"])],
            ["Aligned inputs available", e(time_range(row.get("available_at") for row in rows))],
            ["Price snapshot retrieved", e(stamp(history["retrieved_at"]))],
            ["Price availability basis", e(history["availability_basis"])],
            [
                "Quality / alignment",
                f"{len(quality.get('accepted', [])):,} accepted prices; "
                f"{len(quality.get('quarantined', [])):,} quarantined; "
                f"{len(sample['exclusions'])} excluded alignment periods.",
            ],
        ],
        "factor-method",
    )
    methodology += (
        '<div class="methodology"><h3>Model and data conventions</h3><p>'
        "Response = stock simple return minus same-period risk-free return. Mkt-RF is already "
        "the market excess return. SMB measures size; HML measures value; Mom measures momentum. "
        "Source factor percentages are divided by 100 once. "
        f"Covariance: {e(config['covariance'])}; confidence: {percent(config['confidence'])}. "
        "Alpha is not annualized. Adjusted-close ratios, when used, are provider total-return "
        "proxies; dividends are not added again.</p><p>"
        + e(factors["momentum_definition"])
        + "</p><p>Generation time is the report export clock. The sample interval identifies "
        "the observations being explained. Retrieval/availability metadata do not independently "
        "certify historical publication times or point-in-time membership.</p></div>"
    )
    warnings = list(data["warnings"]) + [w for fit in fits.values() for w in fit["warnings"]]
    methodology += "<h3>Warnings &amp; limitations</h3>" + bullets(warnings)
    methodology += "<h3>Audit downloads</h3>" + downloads(
        [
            ("analysis.json", "Full analysis JSON"),
            ("coefficients.csv", "Coefficients CSV"),
            ("rolling.csv", "Rolling windows CSV"),
            ("aligned.csv", "Aligned data CSV"),
            ("quality.json", "Quality JSON"),
            ("alignment.json", "Exclusions JSON"),
            ("factor_snapshot.json", "Factor inputs"),
            ("price_snapshot.json", "Price inputs"),
            ("run.json", "Provenance / manifest"),
        ]
    )
    return document(
        "Factor Research Report",
        run_id,
        generated_at,
        badges,
        [
            (
                "Security",
                data["returns"]["asset"]["symbol"] + " / " + data["returns"]["asset"]["exchange"],
            ),
            ("Sample interval", interval),
            ("Frequency", config["frequency"]),
        ],
        section("Factor Overview", overview, "overview", "01 / Overview")
        + section("Coefficients & Statistical Evidence", details, "details", "02 / Details", True)
        + section("Data & Methodology", methodology, "methodology", "03 / Methodology", True),
    )
