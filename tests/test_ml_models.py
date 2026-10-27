"""Numerical metrics/Lasso reference and training-only preprocessing checks."""

import importlib
import json
from dataclasses import replace

import numpy as np
import pytest

from portfolio_research_desk.errors import DataError
from portfolio_research_desk.ml_config import MLConfig
from portfolio_research_desk.ml_data import build_samples, synthetic_ml_dataset
from portfolio_research_desk.ml_models import (
    classification_metrics,
    fit_model,
    make_pipeline,
    predict_scores,
    require_ml_dependencies,
)
from portfolio_research_desk.ml_validation import walk_forward_folds
from portfolio_research_desk.ml_workflow import tune_model


@pytest.fixture(scope="module")
def data():
    samples = build_samples(synthetic_ml_dataset())
    return samples, walk_forward_folds(samples, MLConfig())[0]


def test_metrics_against_manual_confusion_and_pairwise_auc():
    target = [0, 0, 1, 1, 0, 1]
    scores = [0.1, 0.8, 0.8, 0.9, 0.2, 0.3]
    result = classification_metrics(target, scores)
    assert result["confusion_matrix"] == [[2, 1], [1, 2]]
    for name in ("accuracy", "precision", "recall", "f1"):
        assert result[name] == pytest.approx(2 / 3)
    wins = sum(
        (a > b) + 0.5 * (a == b)
        for y, a in zip(target, scores, strict=True)
        if y
        for z, b in zip(target, scores, strict=True)
        if not z
    )
    assert result["roc_auc"] == pytest.approx(wins / 9)
    assert classification_metrics([0, 0], [0.1, 0.2])["roc_auc"] is None
    assert classification_metrics([0, 0], [0.1, 0.2])["f1"] == 0
    assert classification_metrics([1, 1], [0.1, 0.2])["recall"] == 0


def test_lasso_against_independent_soft_threshold_solution():
    x = np.linspace(-2, 2, 101)
    matrix = np.column_stack([x, *[np.ones(101) for _ in range(6)]])
    y = 0.02 * x + 0.005
    pipeline = make_pipeline("lasso", {"alpha": 0.001}, 42)
    pipeline.fit(matrix, y)
    sigma = np.sqrt(sum(x**2) / len(x))
    beta = max(0.02 * sigma - 0.001, 0)
    assert pipeline.named_steps["model"].coef_ == pytest.approx([beta])
    assert pipeline.predict(matrix) == pytest.approx(beta * x / sigma + 0.005)
    assert pipeline.named_steps["selection"].get_support().tolist() == [True] + [False] * 6


@pytest.mark.parametrize("model", ["dummy", "logistic", "lasso", "random_forest", "xgboost"])
def test_training_statistics_and_tuning_ignore_outer_test_distributions(data, model):
    samples, fold = data
    config = MLConfig(models=(model,))
    parameters, trials = tune_model(model, samples, fold, config)
    pipeline, audit = fit_model(model, parameters, 42, samples, fold)
    changed = tuple(
        replace(s, feature=replace(s.feature, values=tuple(x * 50 + 999 for x in s.feature.values)))
        if i in fold.test
        else s
        for i, s in enumerate(samples)
    )
    other_parameters, other_trials = tune_model(model, changed, fold, config)
    other_pipeline, other_audit = fit_model(model, other_parameters, 42, changed, fold)
    assert audit == other_audit
    assert parameters == other_parameters
    assert trials == other_trials
    assert audit["scaler_mean"] == pytest.approx(
        np.mean([samples[i].feature.values for i in fold.train], axis=0)
    )
    assert predict_scores(pipeline, model, [samples[i] for i in fold.test]) == predict_scores(
        other_pipeline, model, [samples[i] for i in fold.test]
    )
    json.dumps(audit, allow_nan=False)


@pytest.mark.parametrize("model", ["dummy", "logistic", "lasso", "random_forest", "xgboost"])
def test_outer_validation_labels_cannot_select_inner_parameters_or_fit(data, model):
    samples, fold = data
    config = MLConfig(models=(model,))
    parameters, trials = tune_model(model, samples, fold, config)
    pipeline, audit = fit_model(model, parameters, config.seed, samples, fold)
    changed = tuple(
        replace(s, label=replace(s.label, forward_return=-0.2 if s.label.target else 0.2))
        if i in fold.test and s.label
        else s
        for i, s in enumerate(samples)
    )
    assert any(samples[i].label.target != changed[i].label.target for i in fold.test)
    other_parameters, other_trials = tune_model(model, changed, fold, config)
    other_pipeline, other_audit = fit_model(model, other_parameters, config.seed, changed, fold)
    assert (parameters, trials, audit) == (other_parameters, other_trials, other_audit)
    rows = [samples[i] for i in fold.test]
    assert predict_scores(pipeline, model, rows) == predict_scores(other_pipeline, model, rows)


@pytest.mark.parametrize("model", ["logistic", "random_forest", "xgboost"])
@pytest.mark.parametrize("target", [0, 1])
def test_single_class_training_uses_explicit_prior_fallback(data, model, target):
    samples, fold = data
    samples = tuple(
        replace(s, label=replace(s.label, forward_return=0.01 if target else -0.01))
        if s.label
        else s
        for s in samples
    )
    pipeline, audit = fit_model(model, {}, 42, samples, fold)
    assert audit["actual_model"] == "dummy" and audit["fallback_reason"]
    assert predict_scores(pipeline, model, [samples[fold.test[0]]]) == [float(target)]


def test_imputer_uses_train_median_and_never_refits_on_predict():
    pipeline = make_pipeline("dummy", {}, 42)
    x = [[1, float("nan")], [3, 10], [5, 20]]
    pipeline.fit(x, [0, 1, 1])
    assert pipeline.named_steps["imputer"].statistics_.tolist() == [3, 15]
    before = pipeline.named_steps["scaler"].mean_.copy()
    pipeline.predict_proba([[1000, -1000]])
    assert np.array_equal(before, pipeline.named_steps["scaler"].mean_)


def test_dependency_failure_is_a_user_error(monkeypatch):
    def missing(name):
        raise ImportError(name)

    monkeypatch.setattr(importlib, "import_module", missing)
    with pytest.raises(DataError, match="ml extra"):
        require_ml_dependencies(("xgboost",))


@pytest.mark.parametrize("target,score", [([], []), ([1], []), ([2], [0.3]), ([0], [float("nan")])])
def test_invalid_metrics(target, score):
    with pytest.raises(DataError):
        classification_metrics(target, score)
