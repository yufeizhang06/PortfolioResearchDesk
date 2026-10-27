"""Small seeded model grids; all learned transforms live inside the training pipeline."""

import importlib
import math
import warnings

from portfolio_research_desk.errors import DataError
from portfolio_research_desk.ml_data import Sample
from portfolio_research_desk.ml_validation import Fold, validate_fold


def require_ml_dependencies(models: tuple[str, ...]) -> None:
    try:
        for name in ("numpy", "sklearn", "threadpoolctl") + (
            ("xgboost",) if "xgboost" in models else ()
        ):
            importlib.import_module(name)
    except (ImportError, OSError) as exc:
        raise DataError("Install the ml extra with uv sync --locked --extra ml.") from exc


def candidates(model: str) -> tuple[dict, ...]:
    grids = {
        "dummy": ({},),
        "logistic": ({"C": 0.1}, {"C": 1.0}),
        "lasso": ({"alpha": 0.0001}, {"alpha": 0.001}),
        "random_forest": ({"max_depth": 2}, {"max_depth": 4}),
        "xgboost": ({"max_depth": 1}, {"max_depth": 2}),
    }
    if model not in grids:
        raise DataError("Unknown ML model.")
    return grids[model]


def make_pipeline(model: str, parameters: dict, seed: int):
    from sklearn.dummy import DummyClassifier
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_selection import VarianceThreshold
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Lasso, LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    if model == "dummy":
        estimator = DummyClassifier(strategy="prior")
    elif model == "logistic":
        estimator = LogisticRegression(**parameters, max_iter=2000, random_state=seed)
    elif model == "lasso":
        # Actual Lasso regression of continuous forward returns, not an L1 classifier.
        estimator = Lasso(**parameters, max_iter=10000, tol=1e-8)
    elif model == "random_forest":
        estimator = RandomForestClassifier(
            **parameters, n_estimators=40, min_samples_leaf=5, random_state=seed, n_jobs=1
        )
    elif model == "xgboost":
        from xgboost import XGBClassifier

        estimator = XGBClassifier(
            **parameters,
            n_estimators=40,
            learning_rate=0.05,
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            device="cpu",
            random_state=seed,
            n_jobs=1,
        )
    else:
        raise DataError("Unknown ML model.")
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", StandardScaler()),
            ("selection", VarianceThreshold()),
            ("model", estimator),
        ]
    )


def fit_model(model: str, parameters: dict, seed: int, samples: tuple[Sample, ...], fold: Fold):
    from sklearn.exceptions import ConvergenceWarning

    validate_fold(samples, fold)
    train = [samples[i] for i in fold.train]
    if any(s.label is None or s.label.known_at > fold.fit_at for s in train):
        raise DataError("Training includes unknown labels.")
    classes = {s.label.target for s in train}
    fallback = model not in {"dummy", "lasso"} and len(classes) < 2
    actual = "dummy" if fallback else model
    pipeline = make_pipeline(actual, {} if fallback else parameters, seed)
    y = [s.label.forward_return if model == "lasso" else s.label.target for s in train]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", ConvergenceWarning)
            pipeline.fit([s.feature.values for s in train], y)
    except (ValueError, ConvergenceWarning) as exc:
        raise DataError(f"Model fit failed ({model}): {exc}") from exc
    audit = {
        "requested_model": model,
        "actual_model": actual,
        "parameters": parameters,
        "fallback_reason": "single training class; prior baseline" if fallback else None,
        "training_rows": len(train),
        "training_classes": sorted(classes),
        "imputer_statistics": pipeline.named_steps["imputer"].statistics_.tolist(),
        "scaler_mean": pipeline.named_steps["scaler"].mean_.tolist(),
        "scaler_scale": pipeline.named_steps["scaler"].scale_.tolist(),
        "selected_features": pipeline.named_steps["selection"].get_support().tolist(),
        "estimator_parameters": {
            key: (
                "NaN (native missing marker)"
                if isinstance(value, float) and math.isnan(value)
                else value
            )
            for key, value in pipeline.named_steps["model"].get_params().items()
        },
    }
    fitted = pipeline.named_steps["model"]
    if hasattr(fitted, "coef_"):
        audit["coefficients"] = fitted.coef_.tolist()
        audit["intercept"] = fitted.intercept_.tolist()
    if hasattr(fitted, "feature_importances_"):
        audit["feature_importances"] = fitted.feature_importances_.tolist()
    return pipeline, audit


def predict_scores(pipeline, model: str, rows: list[Sample]) -> list[float]:
    x = [s.feature.values for s in rows]
    if model == "lasso":
        scores = pipeline.predict(x).tolist()
    else:
        classes = list(pipeline.named_steps["model"].classes_)
        scores = (
            pipeline.predict_proba(x)[:, classes.index(1)].tolist()
            if 1 in classes
            else [0.0] * len(x)
        )
    if any(not math.isfinite(value) for value in scores):
        raise DataError("Nonfinite model predictions.")
    return scores


def classification_metrics(target: list[int], score: list[float], threshold: float = 0.5) -> dict:
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    if len(target) != len(score) or not target:
        raise DataError("Metrics require nonempty aligned targets/scores.")
    if any(y not in (0, 1) for y in target) or any(not math.isfinite(s) for s in score):
        raise DataError("Metrics require binary labels and finite scores.")
    predicted = [int(s > threshold) for s in score]
    auc = float(roc_auc_score(target, score)) if len(set(target)) == 2 else None
    return {
        "nobs": len(target),
        "positive_count": sum(target),
        "threshold": threshold,
        "accuracy": float(accuracy_score(target, predicted)),
        "precision": float(precision_score(target, predicted, zero_division=0)),
        "recall": float(recall_score(target, predicted, zero_division=0)),
        "f1": float(f1_score(target, predicted, zero_division=0)),
        "roc_auc": auc,
        "auc_unavailable_reason": "single class" if auc is None else None,
        "confusion_matrix": confusion_matrix(target, predicted, labels=[0, 1]).tolist(),
        "zero_division_policy": "precision/recall/F1 = 0 when denominator is zero",
    }
