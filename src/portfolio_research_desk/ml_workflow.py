"""Nested development evaluation, frozen final holdout, and shared-engine comparisons."""

from dataclasses import dataclass, replace
from decimal import Decimal

from portfolio_research_desk.backtest import BacktestResult, run_backtest
from portfolio_research_desk.backtest_config import BacktestConfig
from portfolio_research_desk.domain import Signal, fingerprint
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.market_data import MarketDataset
from portfolio_research_desk.ml_config import MLConfig
from portfolio_research_desk.ml_data import (
    FEATURE_NAMES,
    Sample,
    build_samples,
    synthetic_ml_dataset,
)
from portfolio_research_desk.ml_models import (
    candidates,
    classification_metrics,
    fit_model,
    predict_scores,
    require_ml_dependencies,
)
from portfolio_research_desk.ml_validation import (
    Fold,
    evaluation_boundary,
    fold_audit,
    inner_folds,
    walk_forward_folds,
)


@dataclass(frozen=True)
class MLResult:
    config: MLConfig
    dataset: MarketDataset
    samples: tuple[Sample, ...]
    folds: tuple[dict, ...]
    predictions: tuple[dict, ...]
    metrics: dict
    frozen_plan: dict
    backtests: dict[str, BacktestResult]
    cost_sensitivity: dict
    warnings: tuple[str, ...]


def _threshold(model):
    return 0.0 if model == "lasso" else 0.5


def tune_model(model: str, samples: tuple[Sample, ...], outer: Fold, config: MLConfig):
    inner = inner_folds(samples, outer, config)
    trials = []
    for parameters in candidates(model):
        records = []
        for fold in inner:
            pipeline, fitted = fit_model(model, parameters, config.seed, samples, fold)
            rows = [samples[i] for i in fold.test]
            scores = predict_scores(pipeline, model, rows)
            metrics = classification_metrics(
                [s.label.target for s in rows], scores, _threshold(model)
            )
            records.append({"fold": fold_audit(fold, samples), "fit": fitted, "metrics": metrics})
        # Fixed F1 objective; ties select the first candidate. Outer labels never enter tuning.
        mean_f1 = sum(r["metrics"]["f1"] for r in records) / len(records)
        trials.append({"parameters": parameters, "mean_f1": mean_f1, "inner_folds": records})
    winner = max(range(len(trials)), key=lambda index: trials[index]["mean_f1"])
    return trials[winner]["parameters"], trials


def _predictions(model, pipeline, samples, fold, evaluation_cutoff=None):
    rows = [samples[i] for i in fold.test]
    scores = predict_scores(pipeline, model, rows)
    records = []
    for index, sample, score in zip(fold.test, rows, scores, strict=True):
        label = sample.label
        eligible = label is not None and (
            evaluation_cutoff is None
            or (label.end_at < evaluation_cutoff and label.known_at < evaluation_cutoff)
        )
        records.append(
            {
                "sample_index": index,
                "model": model,
                "fold_id": fold.fold_id,
                "stage": fold.stage,
                "asset": sample.feature.asset,
                "decision_at": sample.feature.decision_at,
                "available_at": sample.feature.available_at,
                "fit_at": fold.fit_at,
                "score": score,
                "predicted_class": int(score > _threshold(model)),
                "score_kind": "predicted_price_return"
                if model == "lasso"
                else "uncalibrated_class_score",
                "target": label.target if eligible else None,
                "forward_return": label.forward_return if eligible else None,
                "label_start": label.start_at if eligible else None,
                "label_end": label.end_at if eligible else None,
                "label_known_at": label.known_at if eligible else None,
                "exclusion": None
                if eligible
                else ("label_crosses_final_holdout" if label else "forward_label_unavailable"),
            }
        )
    return records


def _metrics(records, model):
    eligible = [r for r in records if r["target"] is not None]
    if not eligible:
        return {
            "nobs": 0,
            "predictions": len(records),
            "excluded": len(records),
            "unavailable_reason": "no complete labels",
        }
    return {
        **classification_metrics(
            [r["target"] for r in eligible], [r["score"] for r in eligible], _threshold(model)
        ),
        "predictions": len(records),
        "excluded": len(records) - len(eligible),
    }


def _portfolio_comparisons(dataset, samples, predictions, config):
    backtests, sensitivity = {}, {}
    by_time = {}
    for sample in samples:
        by_time.setdefault(sample.feature.decision_at, []).append(sample)
    for stage in ("development", "holdout"):
        stage_predictions = [p for p in predictions if p["stage"] == stage]
        dates = sorted({p["decision_at"] for p in stage_predictions})
        end = dates[-1]
        panel = replace(
            dataset,
            sessions=tuple(s for s in dataset.sessions if s.decision_at <= end),
            bars=tuple(b for b in dataset.bars if b.session_date <= end.date()),
        )
        rebalance = set(dates[:: config.horizon])
        for model in (*config.models, "cash", "equal_weight", "buy_hold", "momentum"):
            scores = {
                (p["decision_at"], p["asset"]): p["score"]
                for p in stage_predictions
                if p["model"] == model
            }

            def provider(decision_at, model=model, scores=scores, rebalance=rebalance, dates=dates):
                if decision_at not in rebalance or (
                    model == "buy_hold" and decision_at != dates[0]
                ):
                    return None
                if model == "cash":
                    return ()
                rows = by_time[decision_at]
                return tuple(
                    Signal(
                        s.feature.asset,
                        decision_at,
                        s.feature.observation_start,
                        s.feature.observation_end,
                        s.feature.available_at,
                        Decimal(
                            str(
                                scores[(decision_at, s.feature.asset)]
                                if model in config.models
                                else s.feature.values[1]
                                if model == "momentum"
                                else 0
                            )
                        ),
                    )
                    for s in rows
                )

            settings = BacktestConfig(
                lookback_sessions=1, top_k=3 if model in {"equal_weight", "buy_hold"} else 2
            )
            key = f"{stage}/{model}"
            result = run_backtest(settings, panel, provider)
            backtests[key] = result
            sensitivity[key] = {"base": result.metrics}
            for multiplier in (0, 2):
                scenario = replace(
                    settings,
                    commission_bps=settings.commission_bps * multiplier,
                    fixed_fee=settings.fixed_fee * multiplier,
                    slippage_bps=settings.slippage_bps * multiplier,
                )
                sensitivity[key][f"cost_x{multiplier}"] = run_backtest(
                    scenario, panel, provider
                ).metrics
    return backtests, sensitivity


def run_ml_experiment(config: MLConfig, dataset: MarketDataset | None = None) -> MLResult:
    require_ml_dependencies(config.models)
    from threadpoolctl import threadpool_limits

    with threadpool_limits(limits=1):
        return _run(config, dataset)


def _run(config, dataset):
    dataset = synthetic_ml_dataset(config.sessions) if dataset is None else dataset
    if len(dataset.sessions) != config.sessions:
        raise DataError("Dataset session count differs from frozen configuration.")
    samples = build_samples(dataset, config.horizon)
    folds = walk_forward_folds(samples, config)
    final = folds[-1]
    predictions, audits = [], []
    for fold in folds[:-1]:
        for model in config.models:
            parameters, trials = tune_model(model, samples, fold, config)
            pipeline, fitted = fit_model(model, parameters, config.seed, samples, fold)
            records = _predictions(
                model, pipeline, samples, fold, evaluation_boundary(final.fit_at)
            )
            predictions.extend(records)
            audits.append(
                {
                    "fold": fold_audit(fold, samples),
                    "model": model,
                    "trials": trials,
                    "selected_parameters": parameters,
                    "fit": fitted,
                    "metrics": _metrics(records, model),
                }
            )
    metrics = {"development": {}, "holdout": {}}
    for model in config.models:
        metrics["development"][model] = _metrics(
            [p for p in predictions if p["model"] == model], model
        )
    selected_model = max(config.models, key=lambda m: metrics["development"][m].get("f1", -1))
    # Freeze parameters and development winner BEFORE predicting the holdout.
    final_parameters, final_trials = {}, {}
    for model in config.models:
        final_parameters[model], final_trials[model] = tune_model(model, samples, final, config)
    frozen = {
        "config_hash": fingerprint(config.snapshot()),
        "feature_names": FEATURE_NAMES,
        "label": "next open -> open horizon sessions later; price return > 0",
        "selected_model": selected_model,
        "parameters": final_parameters,
        "selection_metric": "development pooled F1; ties follow configured model order",
        "fit_at": final.fit_at,
        "holdout_policy": "one frozen fit per model, no holdout tuning",
        "rebalance_sessions": config.horizon,
        "thresholds": {m: _threshold(m) for m in config.models},
    }
    frozen["plan_hash"] = fingerprint(frozen)
    for model in config.models:
        pipeline, fitted = fit_model(model, final_parameters[model], config.seed, samples, final)
        records = _predictions(model, pipeline, samples, final)
        predictions.extend(records)
        metrics["holdout"][model] = _metrics(records, model)
        audits.append(
            {
                "fold": fold_audit(final, samples),
                "model": model,
                "trials": final_trials[model],
                "selected_parameters": final_parameters[model],
                "fit": fitted,
                "metrics": _metrics(records, model),
            }
        )
    backtests, sensitivity = _portfolio_comparisons(dataset, samples, predictions, config)
    return MLResult(
        config,
        dataset,
        samples,
        tuple(audits),
        tuple(predictions),
        metrics,
        frozen,
        backtests,
        sensitivity,
        (
            "SYNTHETIC USD implementation validation only; no credible real-market OOS claim.",
            "Fixed synthetic universe; no real PIT membership, delisting or "
            "corporate-action coverage.",
            "No Phase 3 factors, fundamental or industry data enter features.",
            "Classifier scores are uncalibrated; Lasso scores are "
            "continuous price-return estimates.",
            "Overlapping labels/serial dependence: metrics are descriptive, "
            "no IID significance claim.",
            "Incomplete/cross-holdout labels excluded explicitly; prediction coverage is retained.",
            "Embargo is an extra pre-test safety buffer; forward-only folds "
            "never train after their test.",
            "Top-K ranks all scores, even negative Lasso scores; threshold "
            "only affects classification metrics.",
            "Holdout comparison shows all predeclared models; "
            "selected_model was frozen on development.",
            "End NAV marks open holdings; no forced final liquidation; "
            "label return differs from net P&L.",
            "Repeated synthetic runs test software only; a future real "
            "holdout needs a new frozen protocol.",
        ),
    )
