"""Classification and portfolio evidence from saved ML results, without refitting."""

from portfolio_research_desk.report_design import (
    bullets,
    document,
    downloads,
    e,
    line_chart,
    metric,
    money,
    notice,
    number,
    percent,
    section,
    stamp,
    table,
    time_range,
)

MODEL_NAMES = {
    "dummy": "Prior baseline",
    "logistic": "Logistic regression",
    "lasso": "Lasso",
    "random_forest": "Random forest",
    "xgboost": "XGBoost",
    "cash": "Cash",
    "buy_hold": "Buy & hold",
    "equal_weight": "Equal weight",
    "momentum": "Momentum",
}


def model_name(name):
    return MODEL_NAMES.get(name, name)


def _classification(metrics, models, stage):
    rows = []
    for model in models:
        if model not in metrics:
            continue
        m = metrics[model]
        auc = number(m["roc_auc"], 3)
        if m.get("auc_unavailable_reason"):
            auc += f"<small>{e(m['auc_unavailable_reason'])}</small>"
        rows.append(
            [
                e(model_name(model)),
                percent(m["accuracy"]),
                number(m["f1"], 3),
                auc,
                percent(m["precision"]),
                percent(m["recall"]),
                f"{m['nobs']:,} / {m['predictions']:,}",
                f"{m['excluded']:,}",
            ]
        )
    return table(
        (
            "Model",
            "Accuracy",
            "F1",
            "ROC-AUC",
            "Precision",
            "Recall",
            "Scored / predicted",
            "Excluded",
        ),
        rows,
        f"ml-{stage}",
        tuple(range(1, 8)),
    )


def render_ml_report(data, run_id, generated_at):
    config, frozen, metrics = data["config"], data["frozen_plan"], data["metrics"]
    selected = frozen["selected_model"]
    models = list(
        dict.fromkeys(
            [*config["models"], *metrics.get("development", {}), *metrics.get("holdout", {})]
        )
    )
    held = metrics.get("holdout", {}).get(selected, {})
    folds = [r for r in data["folds"] if r["model"] == selected]
    interval = "No evaluation folds recorded"
    if folds:
        interval = f"{min(r['fold']['test_start'] for r in folds)[:10]} to "
        interval += max(r["fold"]["test_end"] for r in folds)[:10]
    overview = notice(
        "SYNTHETIC USD software validation. Out-of-sample here describes the "
        "synthetic test split, not verified real-market performance or a profitable strategy.",
        True,
    )
    overview += (
        '<div class="metrics">'
        + "".join(
            (
                metric(
                    "Frozen model",
                    model_name(selected),
                    "Chosen using development only",
                    "ml-selected",
                    True,
                ),
                metric(
                    "Holdout accuracy",
                    percent(held.get("accuracy")),
                    "Correct direction classifications",
                    "ml-accuracy",
                ),
                metric(
                    "Holdout F1",
                    number(held.get("f1"), 3),
                    "Precision / recall balance (0 to 1)",
                    "ml-f1",
                ),
                metric(
                    "Holdout ROC-AUC",
                    number(held.get("roc_auc"), 3),
                    "Ranking score (0.5 is chance)",
                    "ml-auc",
                ),
            )
        )
        + "</div>"
    )
    overview += '<p class="section-intro">The frozen model remains highlighted even if another '
    overview += (
        "model scores higher in the holdout. Classification quality and portfolio returns "
        "measure different things; neither establishes future profitability.</p>"
    )
    overview += "<h2>Development: Walk-Forward Comparison</h2>"
    overview += _classification(metrics.get("development", {}), models, "development")
    overview += "<h2>Final Holdout: Frozen Comparison</h2>"
    overview += _classification(metrics.get("holdout", {}), models, "holdout")
    overview += (
        '<p class="note">Accuracy: correct predictions / scored labels. Precision: correct '
        "positive predictions / predicted positives. Recall: positive labels found. F1 is their "
        "harmonic mean. ROC-AUC measures ranking across thresholds and is unavailable with "
        "one label class. Missing and boundary-crossing labels are excluded, never scored as zero. "
        "Scores are uncalibrated; Lasso predicts a continuous price return.</p>"
    )

    fold_rows = []
    for record in folds:
        f, m = record["fold"], record["metrics"]
        fold_rows.append(
            [
                e(f["fold_id"]),
                e(f["train_start"][:10] + " to " + f["train_end"][:10]),
                e(f["test_start"][:10] + " to " + f["test_end"][:10]),
                f"{len(f['train_indices']):,}",
                f"{len(f['purged_indices']):,}",
                f"{m['nobs']:,}",
                number(m["f1"], 3),
            ]
        )
    validation = '<p class="section-intro">Dates are grouped globally across assets. Each model '
    validation += (
        "fits only earlier training data. Overlapping labels are purged and extra gap/embargo "
        "dates are buffered. Final holdout uses one frozen fit per model.</p>"
    )
    validation += table(
        ("Fold", "Training dates", "Evaluation dates", "Train rows", "Purged", "Scored", "F1"),
        fold_rows,
        "ml-folds",
        (3, 4, 5, 6),
    )
    validation += (
        f'<p class="note">Boundary table: {e(model_name(selected))}, the frozen selection. '
    )
    validation += "All other models and inner folds remain in folds.json.</p>"
    dev_folds = [r["fold"]["fold_id"] for r in folds if r["fold"]["stage"] == "development"]
    records = {(r["model"], r["fold"]["fold_id"]): r for r in data["folds"]}
    validation += line_chart(
        dev_folds,
        [
            (
                model_name(model),
                [records.get((model, fold), {}).get("metrics", {}).get("f1") for fold in dev_folds],
            )
            for model in models
        ],
        "ml-fold-chart",
        "Development fold F1, all predeclared models",
        lambda v: number(v, 2),
        note="Development F1 by outer fold. All predeclared models; no holdout tuning.",
    )
    confusion = held.get("confusion_matrix")
    if confusion is not None:
        validation += "<h3>Frozen model: holdout confusion matrix</h3>" + table(
            ("Actual direction", "Predicted non-positive", "Predicted positive"),
            [
                ["Non-positive", str(confusion[0][0]), str(confusion[0][1])],
                ["Positive", str(confusion[1][0]), str(confusion[1][1])],
            ],
            "ml-confusion",
            (1, 2),
        )
    reasons = [
        r["fit"]["fallback_reason"] for r in data["folds"] if r["fit"].get("fallback_reason")
    ]
    if reasons:
        validation += "<h3>Model fallbacks</h3>" + bullets(reasons)

    portfolios = data["portfolios"]
    portfolio_rows = []
    for key, p in portfolios.items():
        stage, model = key.split("/", 1)
        m = p["metrics"]
        portfolio_rows.append(
            [
                e(stage + " / " + model_name(model)),
                money(m["ending_nav"], "USD"),
                percent(m["cumulative_return"]),
                percent(m["max_drawdown"]),
                money(m["total_commission"], "USD"),
                money(m["total_slippage_cost"], "USD"),
                str(m["fill_count"]),
            ]
        )
    portfolio = notice(
        "Each strategy starts each stage with separate capital. Development and "
        "holdout NAV are not stitched into one return. Costs are already included in NAV.",
        True,
    )
    portfolio += table(
        (
            "Stage / strategy",
            "Ending NAV",
            "Net return",
            "Max drawdown",
            "Commission",
            "Slippage",
            "Fills",
        ),
        portfolio_rows,
        "ml-portfolios",
        (1, 2, 3, 4, 5, 6),
    )
    charts = "<h2>Holdout NAV &amp; Cost Sensitivity</h2>"
    selected_portfolio = portfolios.get("holdout/" + selected)
    if selected_portfolio:
        holdout = [r["fold"] for r in folds if r["fold"]["stage"] == "holdout"]
        labels = [
            p["session_date"]
            for p in selected_portfolio["equity"]
            if not holdout
            or holdout[0]["test_start"][:10] <= p["session_date"] <= holdout[0]["test_end"][:10]
        ]
        series = []
        for name in dict.fromkeys((selected, "cash", "buy_hold", "equal_weight", "momentum")):
            bt = portfolios.get("holdout/" + name)
            if bt:
                by_date = {p["session_date"]: p["nav"] for p in bt["equity"]}
                series.append((model_name(name), [by_date.get(date) for date in labels]))
        charts += line_chart(
            labels,
            series,
            "ml-nav",
            "Holdout NAV: frozen model and baselines",
            lambda v: number(v, 0),
            note="USD NAV, zoomed to the final holdout evaluation dates. "
            "Earlier cash-only fixture sessions remain in the full ledger. "
            "The comparison table includes every model.",
        )
    sensitivity_rows = []
    for stage in ("development", "holdout"):
        for scenario, m in data["cost_sensitivity"].get(f"{stage}/{selected}", {}).items():
            sensitivity_rows.append(
                [
                    e(stage),
                    e(scenario),
                    percent(m["cumulative_return"]),
                    money(m["total_commission"], "USD"),
                    money(m["total_slippage_cost"], "USD"),
                ]
            )
    charts += "<h3>Frozen model: cost sensitivity</h3>" + table(
        ("Stage", "Cost scenario", "Net return", "Commission", "Slippage"),
        sensitivity_rows,
        "ml-costs",
        (2, 3, 4),
    )
    charts += (
        '<p class="note">cost_x0 / base / cost_x2 are recorded zero/base/double-cost reruns, '
        "not arithmetic fee deductions. Integer sizing can change. Cash earns no interest; "
        "buy-hold/equal-weight hold all fixture assets; momentum/models use Top-K. "
        "Annualized return, volatility and Sharpe are not supplied by this validation engine.</p>"
    )

    portfolio += f'<div class="print-page">{charts}</div>'
    bars = data["dataset"]["bars"]
    methodology = table(
        ("Protocol", "Recorded setting"),
        [
            ["Model selection", e(frozen["selection_metric"])],
            ["Frozen fit at", e(stamp(frozen["fit_at"]))],
            ["Label", e(frozen["label"])],
            ["Features", e(", ".join(frozen["feature_names"]))],
            [
                "Validation settings",
                f"{config['min_train_dates']} minimum training dates; "
                f"{config['validation_dates']} validation dates; "
                f"{config['holdout_dates']} holdout dates; "
                f"{config['gap_dates']} gap; {config['embargo_dates']} embargo; "
                f"{config['inner_splits']} inner splits.",
            ],
            ["Seed / data source", e(f"{config['seed']} / {data['dataset']['source']}")],
            [
                "Price inputs available",
                e(time_range(row.get("available_at") for row in bars)),
            ],
            [
                "Score thresholds",
                e(
                    "; ".join(
                        f"{model_name(name)}: {number(value, 2)}"
                        for name, value in frozen["thresholds"].items()
                    )
                ),
            ],
        ],
        "ml-method",
    )
    methodology += (
        '<div class="methodology"><p>Imputation, scaling and variance selection are fit '
        "only within training windows. Inner time-series splits tune candidate parameters; "
        "outer folds evaluate development predictions. The holdout comparison retains all "
        "predeclared models but cannot replace the development-frozen selection.</p>"
        "<p>Generation time is an export clock. Fit and evaluation dates are experiment "
        "clocks. Input availability is supplied fixture metadata; this is not a certification "
        "of historical market data. Repeated synthetic holdout runs are software regressions, "
        "not an untouched real research holdout.</p></div>"
    )
    methodology += "<h3>Limits and warnings</h3>" + bullets(data["warnings"])
    methodology += "<h3>Audit downloads</h3>" + downloads(
        [
            ("metrics.json", "Classification metrics"),
            ("predictions.csv", "Predictions CSV"),
            ("folds.json", "All fold audits"),
            ("frozen_plan.json", "Frozen protocol"),
            ("portfolio_metrics.csv", "Portfolio metrics CSV"),
            ("portfolios.json", "Full portfolio ledgers"),
            ("cost_sensitivity.json", "Cost scenarios"),
            ("data_snapshot.json", "Data inputs"),
            ("run.json", "Provenance / manifest"),
        ]
    )
    return document(
        "Machine Learning Report",
        run_id,
        generated_at,
        ("SYNTHETIC", "USD", "SOFTWARE VALIDATION"),
        [("Evaluation interval", interval)],
        section("Model Overview", overview, "overview", "01 / Overview")
        + section("Walk-Forward Validation", validation, "details", "02 / Details", True)
        + section("Portfolio Outcomes & Benchmarks", portfolio, "portfolio", page=True)
        + section("Data & Methodology", methodology, "methodology", "03 / Methodology", True),
    )
