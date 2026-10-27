"""Offline integration, future perturbations, audited accounting and report failures."""

import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from portfolio_research_desk.cli import main
from portfolio_research_desk.domain import fingerprint
from portfolio_research_desk.errors import ConfigError, DataError, ReportError
from portfolio_research_desk.ml_config import MLConfig, load_ml_config
from portfolio_research_desk.ml_data import synthetic_ml_dataset
from portfolio_research_desk.ml_reporting import save_ml_report
from portfolio_research_desk.ml_workflow import run_ml_experiment


@pytest.fixture(scope="module")
def result():
    return run_ml_experiment(MLConfig(sessions=240, holdout_dates=20))


def test_all_models_have_identical_oos_coverage_and_auditable_holdout(result):
    assert result.frozen_plan["selected_model"] in result.config.models
    for stage in ("development", "holdout"):
        coverage = []
        for model in result.config.models:
            records = [p for p in result.predictions if p["model"] == model and p["stage"] == stage]
            coverage.append([(p["decision_at"], p["asset"], p["target"]) for p in records])
            assert len({(p["asset"], p["decision_at"]) for p in records}) == len(records)
            assert all(p["available_at"] <= p["decision_at"] for p in records)
        assert all(c == coverage[0] for c in coverage)
    assert all(result.metrics["holdout"][m]["excluded"] == 18 for m in result.config.models)
    final = [f for f in result.folds if f["fold"]["stage"] == "holdout"]
    assert len(final) == len(result.config.models)
    for audit in result.folds:
        for checked in (
            audit["fold"],
            *[item["fold"] for trial in audit["trials"] for item in trial["inner_folds"]],
        ):
            assert checked["latest_train_label_end"] < checked["evaluation_boundary"]
            assert checked["latest_train_label_known_at"] < checked["evaluation_boundary"]
    assert any(p["exclusion"] == "label_crosses_final_holdout" for p in result.predictions)


def test_ml_fills_and_nav_rebuild_independently(result):
    for strategy, backtest in result.backtests.items():
        cash, holdings = backtest.config.initial_cash, {}
        for point in backtest.equity:
            for fill in backtest.fills:
                if fill.execution_at.date() == point.session_date:
                    assert fill.decision_at < fill.execution_at
                    assert fill.decision_at.date() < fill.execution_at.date()
                    sign = 1 if fill.side == "BUY" else -1
                    cash -= sign * fill.quantity * fill.price + fill.commission
                    holdings[fill.asset] = holdings.get(fill.asset, 0) + sign * fill.quantity
            marks = {
                b.asset: b.close
                for b in result.dataset.bars
                if b.session_date == point.session_date
            }
            assert point.nav == cash + sum((marks[a] * q for a, q in holdings.items()), Decimal(0))
            assert cash == point.cash and cash >= 0
        assert result.cost_sensitivity[strategy]["base"] == backtest.metrics
        assert set(result.cost_sensitivity[strategy]) == {"base", "cost_x0", "cost_x2"}
        if strategy.endswith("/cash"):
            assert not backtest.fills and backtest.metrics["cumulative_return"] == 0


def test_holdout_prices_cannot_change_development_or_frozen_selection():
    config = MLConfig(sessions=240, holdout_dates=20, models=("logistic", "lasso"))
    dataset = synthetic_ml_dataset(config.sessions)
    original = run_ml_experiment(config, dataset)
    cutoff = original.frozen_plan["fit_at"].date()
    changed = replace(
        dataset,
        bars=tuple(
            replace(b, open=b.open * 2, high=b.high * 2, low=b.low * 2, close=b.close * 2)
            if b.session_date >= cutoff
            else b
            for b in dataset.bars
        ),
    )
    modified = run_ml_experiment(config, changed)
    assert original.frozen_plan == modified.frozen_plan
    assert original.metrics["development"] == modified.metrics["development"]
    assert [a for a in original.folds if a["fold"]["stage"] == "development"] == [
        a for a in modified.folds if a["fold"]["stage"] == "development"
    ]
    assert [p for p in original.predictions if p["stage"] == "development"] == [
        p for p in modified.predictions if p["stage"] == "development"
    ]
    for model in config.models:
        key = f"development/{model}"
        assert original.backtests[key] == modified.backtests[key]


def test_future_prices_and_labels_do_not_change_earlier_model_signals_and_targets():
    config = MLConfig(sessions=240, holdout_dates=20, models=("logistic",))
    dataset = synthetic_ml_dataset(config.sessions)
    first = run_ml_experiment(config, dataset)
    cutoff = dataset.sessions[180].session_date
    changed = replace(
        dataset,
        bars=tuple(
            replace(b, open=b.open * 3, high=b.high * 3, low=b.low * 3, close=b.close * 3)
            if b.session_date >= cutoff
            else b
            for b in dataset.bars
        ),
    )
    second = run_ml_experiment(config, changed)
    for left, right in zip(first.predictions, second.predictions, strict=True):
        if left["decision_at"].date() < cutoff:
            assert (left["decision_at"], left["score"]) == (right["decision_at"], right["score"])
    assert [
        d
        for d in first.backtests["development/logistic"].decisions
        if d.decision_at.date() < cutoff
    ] == [
        d
        for d in second.backtests["development/logistic"].decisions
        if d.decision_at.date() < cutoff
    ]


def test_report_hashes_ledgers_and_no_overwrite(result, tmp_path):
    directory = save_ml_report(result, tmp_path, "verification")
    marker = json.loads((directory / "run.json").read_text())
    assert marker["credible_real_market_oos"] is False
    assert marker["historical_signal_eligible"] is False
    for name, sha in marker["artifacts"].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == sha
    assert json.loads((directory / "metrics.json").read_text()) == result.metrics
    assert "SYNTHETIC" in (directory / "report.html").read_text("utf-8")
    assert {
        "folds.json",
        "predictions.csv",
        "fills.csv",
        "positions.csv",
        "portfolios.json",
    } <= set(marker["artifacts"])
    with pytest.raises(ReportError, match="never overwritten"):
        save_ml_report(result, tmp_path, "verification")
    for run_id in ("CON", "../bad", "", "a.b"):
        with pytest.raises(ReportError):
            save_ml_report(result, tmp_path, run_id)


def test_report_io_failure_leaves_no_success_marker(result, tmp_path, monkeypatch):
    import portfolio_research_desk.ml_reporting as reporting

    def fail(*args, **kwargs):
        raise OSError("injected disk failure")

    monkeypatch.setattr(reporting, "_write_csv", fail)
    with pytest.raises(ReportError, match="completion marker"):
        reporting.save_ml_report(result, tmp_path, "incomplete")
    assert not (tmp_path / "incomplete/run.json").exists()


def test_cli_json_configuration_and_errors(tmp_path, capsys, monkeypatch, result):
    import portfolio_research_desk.ml_cli as boundary

    assert main(["config", "validate", "--kind", "ml"]) == 0
    assert json.loads(capsys.readouterr().out)["phase"] == 4
    assert load_ml_config() == load_ml_config(Path("configs/example_ml.toml"))
    monkeypatch.setattr(boundary, "run_ml_experiment", lambda config: result)
    assert main(["ml", "run", "--output-dir", str(tmp_path), "--run-id", "cli"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["phase"] == 4 and payload["credible_real_market_oos"] is False
    invalid = tmp_path / "real.toml"
    invalid.write_text('expected_kind="real"')
    with pytest.raises(SystemExit) as error:
        main(["ml", "run", "--config", str(invalid)])
    assert error.value.code == 2 and capsys.readouterr().out == ""
    assert not (tmp_path / "failure/run.json").exists()


@pytest.mark.parametrize(
    "updates",
    [
        {"sessions": True},
        {"horizon": 0},
        {"gap_dates": -1},
        {"embargo_dates": True},
        {"models": ("unknown",)},
        {"models": ("logistic", "logistic")},
        {"models": ({},)},
        {"models": ()},
        {"inner_splits": 1},
        {"seed": 2**32},
        {"sessions": 100},
        {"min_train_dates": 10},
        {"max_train_dates": 20},
        {"expected_kind": "real"},
        {"schema_version": True},
        {"mode": "paper"},
    ],
)
def test_config_rejects_invalid_or_future_scope(updates):
    with pytest.raises(ConfigError):
        MLConfig(**updates)


def test_invalid_toml_unknown_fields_and_dataset_size(tmp_path):
    path = tmp_path / "bad.toml"
    for contents in ('models="logistic"', "[broken", "extra=1"):
        path.write_text(contents)
        with pytest.raises(ConfigError):
            load_ml_config(path)
    with pytest.raises(ConfigError):
        load_ml_config(tmp_path / "missing")
    with pytest.raises(DataError, match="session count"):
        run_ml_experiment(MLConfig(), synthetic_ml_dataset(100))


def test_frozen_hash_is_self_consistent(result):
    plan = {k: v for k, v in result.frozen_plan.items() if k != "plan_hash"}
    assert fingerprint(plan) == result.frozen_plan["plan_hash"]


def test_future_labels_alone_cannot_change_earlier_scores_and_targets(result, monkeypatch):
    import portfolio_research_desk.ml_workflow as workflow

    cutoff = result.dataset.sessions[180].decision_at
    changed = tuple(
        replace(s, label=replace(s.label, forward_return=-0.02 if s.label.target else 0.02))
        if s.label and s.label.known_at >= cutoff
        else s
        for s in result.samples
    )
    assert any(a != b for a, b in zip(changed, result.samples, strict=True))
    monkeypatch.setattr(workflow, "build_samples", lambda dataset, horizon: changed)
    modified = workflow.run_ml_experiment(result.config, result.dataset)

    def early(value):
        return [
            (p["model"], p["decision_at"], p["asset"], p["score"])
            for p in value.predictions
            if p["decision_at"] < cutoff
        ]

    assert early(result) == early(modified)
    for model in result.config.models:
        key = f"development/{model}"
        assert [d.target for d in result.backtests[key].decisions if d.decision_at < cutoff] == [
            d.target for d in modified.backtests[key].decisions if d.decision_at < cutoff
        ]


def test_holdout_features_and_labels_cannot_change_frozen_plan_or_training(result, monkeypatch):
    import portfolio_research_desk.ml_workflow as workflow

    cutoff = result.frozen_plan["fit_at"]
    changed = tuple(
        replace(
            s,
            feature=replace(s.feature, values=tuple(x * 100 + 500 for x in s.feature.values)),
            label=replace(s.label, forward_return=-0.3 if s.label.target else 0.3)
            if s.label
            else None,
        )
        if s.feature.decision_at >= cutoff
        else s
        for s in result.samples
    )
    assert any(
        a.label.target != b.label.target
        for a, b in zip(result.samples, changed, strict=True)
        if a.label and a.feature.decision_at >= cutoff
    )
    monkeypatch.setattr(workflow, "build_samples", lambda dataset, horizon: changed)
    modified = workflow.run_ml_experiment(result.config, result.dataset)
    assert result.frozen_plan == modified.frozen_plan
    assert result.metrics["development"] == modified.metrics["development"]
    assert result.metrics["holdout"] != modified.metrics["holdout"]
    for before, after in zip(result.folds, modified.folds, strict=True):
        for key in ("fold", "model", "trials", "selected_parameters", "fit"):
            assert before[key] == after[key]
