"""Immutable JSON/CSV/HTML experiment bundle; completion marker is written last."""

import hashlib
import importlib.metadata
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from portfolio_research_desk.domain import fingerprint, jsonable
from portfolio_research_desk.errors import ReportError
from portfolio_research_desk.ml_report_html import render_ml_report
from portfolio_research_desk.ml_workflow import MLResult
from portfolio_research_desk.reporting import _write_csv, _write_json, collect_provenance


def save_ml_report(result: MLResult, output_dir: Path, run_id: str | None = None) -> Path:
    started = datetime.now(UTC)
    run_id = run_id if run_id is not None else f"{started:%Y%m%dT%H%M%S}-{uuid4().hex[:12]}"
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)
    }
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id) or run_id.upper() in reserved:
        raise ReportError("Invalid or reserved ML run_id.")
    directory = output_dir / run_id
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        directory.mkdir(exist_ok=False)
    except OSError as exc:
        raise ReportError(
            "Cannot reserve new ML directory; existing runs are never overwritten."
        ) from exc
    try:
        provenance = collect_provenance()
        # A wheel cannot discover the original lock file: package versions remain explicit.
        provenance.update(
            random_seed=result.config.seed,
            randomness="seeded, CPU, one thread",
            runtime_dependencies={
                name: importlib.metadata.version(name)
                for name in ("numpy", "scikit-learn", "xgboost")
                if name != "xgboost" or "xgboost" in result.config.models
            },
        )
        payloads = {
            "config_snapshot.json": result.config.snapshot(),
            "data_snapshot.json": result.dataset,
            "samples.json": result.samples,
            "folds.json": result.folds,
            "predictions.json": result.predictions,
            "metrics.json": result.metrics,
            "frozen_plan.json": result.frozen_plan,
            "cost_sensitivity.json": result.cost_sensitivity,
        }
        portfolio = {}
        ledgers = {"fills": [], "orders": [], "equity": [], "positions": [], "decisions": []}
        for strategy, backtest in result.backtests.items():
            serialized = jsonable(backtest)
            del serialized["dataset_snapshot"]
            portfolio[strategy] = serialized
            for name in ("fills", "orders", "equity", "decisions"):
                for record in serialized[name]:
                    ledgers[name].append(
                        {"strategy": strategy, "record_json": json.dumps(record, sort_keys=True)}
                    )
            for point in serialized["equity"]:
                for position in point["positions"]:
                    ledgers["positions"].append(
                        {
                            "strategy": strategy,
                            "record_json": json.dumps(
                                {"valuation_at": point["valuation_at"], **position}, sort_keys=True
                            ),
                        }
                    )
        payloads["portfolios.json"] = portfolio
        for name, payload in payloads.items():
            _write_json(directory / name, payload)
        predictions = []
        for record in jsonable(result.predictions):
            record["asset"] = ":".join(
                record["asset"][key] for key in ("market", "exchange", "symbol", "currency")
            )
            predictions.append(record)
        _write_csv(directory / "predictions.csv", list(predictions[0]), predictions)
        for name, records in ledgers.items():
            _write_csv(directory / f"{name}.csv", ["strategy", "record_json"], records)
        comparison = [
            {"strategy": name, **jsonable(bt.metrics)} for name, bt in result.backtests.items()
        ]
        _write_csv(directory / "portfolio_metrics.csv", list(comparison[0]), comparison)
        contents = render_ml_report(
            {
                "config": result.config.snapshot(),
                "dataset": jsonable(result.dataset),
                "metrics": result.metrics,
                "folds": jsonable(result.folds),
                "frozen_plan": jsonable(result.frozen_plan),
                "portfolios": portfolio,
                "cost_sensitivity": jsonable(result.cost_sensitivity),
                "warnings": result.warnings,
            },
            run_id,
            started,
        )
        (directory / "report.html").write_text(contents, encoding="utf-8", newline="\n")
        hashes = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.iterdir())
        }
        _write_json(
            directory / "run.json",
            {
                "phase": 4,
                "schema_version": 1,
                "status": "complete",
                "run_id": run_id,
                "run_started_at": started,
                "data_kind": "synthetic",
                "historical_signal_eligible": False,
                "credible_real_market_oos": False,
                "data_snapshot_hash": result.dataset.data_hash,
                "config_hash": fingerprint(result.config.snapshot()),
                "warnings": result.warnings,
                "frozen_plan_hash": result.frozen_plan["plan_hash"],
                "artifacts": hashes,
                **provenance,
            },
        )
    except OSError as exc:
        raise ReportError("Incomplete ML bundle; completion marker was not written.") from exc
    return directory
