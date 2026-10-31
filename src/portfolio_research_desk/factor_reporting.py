"""Auditable factor bundles: shared provenance, finite JSON/CSV, HTML and static figures."""

import csv
import hashlib
import json
import re
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from portfolio_research_desk.domain import fingerprint, jsonable
from portfolio_research_desk.errors import DataError, ReportError
from portfolio_research_desk.factor_data import FACTOR_NAMES
from portfolio_research_desk.factor_report_html import render_factor_report
from portfolio_research_desk.factor_workflow import FactorRun
from portfolio_research_desk.reporting import collect_provenance


def _json(path, payload):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(jsonable(payload), stream, indent=2, sort_keys=True, allow_nan=False)


def _csv(path, rows, fields):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        writer.writerows(rows)


def _charts(result: FactorRun, directory: Path) -> list[str]:
    if not result.comparison:
        return []
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as exc:
        raise DataError("Install factors extra to export factor charts.") from exc
    outputs = []
    with plt.rc_context({"svg.hashsalt": "PortfolioResearchDesk", "font.size": 10}):
        values = [
            [
                result.comparison["fits"][model]["coefficients"][name]["estimate"]
                if name in result.comparison["fits"][model]["coefficients"]
                else np.nan
                for name in FACTOR_NAMES
            ]
            for model in ("FF3", "FF4")
        ]
        fig, ax = plt.subplots(figsize=(8, 3), layout="constrained")
        limit = max(0.1, float(np.nanmax(np.abs(values))))
        chart = ax.imshow(values, cmap="RdBu_r", vmin=-limit, vmax=limit, aspect="auto")
        ax.set_xticks(range(4), FACTOR_NAMES)
        ax.set_yticks(range(2), ["FF3", "Carhart FF4"])
        for i in range(2):
            for j in range(4):
                ax.text(
                    j,
                    i,
                    "N/A" if np.isnan(values[i][j]) else f"{values[i][j]:.3f}",
                    ha="center",
                    color="white" if abs(values[i][j]) > 0.6 * limit else "black",
                )
        ax.set_title("Factor betas | identical sample | descriptive attribution")
        fig.colorbar(chart, ax=ax, label="Beta (dimensionless)")
        fig.savefig(directory / "exposure.svg", metadata={"Date": None})
        fig.savefig(directory / "exposure.png", dpi=150)
        plt.close(fig)
        outputs.append("exposure.svg")
        if result.rolling:
            fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
            dates = [datetime.fromisoformat(r["window_end"]) for r in result.rolling]
            for name in FACTOR_NAMES:
                values = [
                    r["comparison"]["fits"]["FF4"]["coefficients"][name]["estimate"]
                    if r["status"] == "complete"
                    else np.nan
                    for r in result.rolling
                ]
                ax.plot(dates, values, label=name)
            ax.axhline(0, color="gray", linewidth=0.5)
            ax.set(
                title=f"Trailing {result.config.rolling_window}-period FF4 exposures | ex-post",
                xlabel="Window end",
                ylabel="Beta (dimensionless)",
            )
            ax.legend(ncol=4)
            fig.autofmt_xdate()
            fig.savefig(directory / "rolling.svg", metadata={"Date": None})
            fig.savefig(directory / "rolling.png", dpi=150)
            plt.close(fig)
            outputs.append("rolling.svg")
    return outputs


def save_factor_report(result: FactorRun, output_dir: Path, run_id: str | None = None) -> Path:
    generated_at = datetime.now(UTC)
    run_id = run_id or f"{generated_at:%Y%m%dT%H%M%S}-{uuid4().hex[:12]}"
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)
    }
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id) or run_id.upper() in reserved:
        raise ReportError("Unsafe/reserved factor run_id.")
    directory = output_dir / run_id
    try:
        directory.mkdir(parents=True, exist_ok=False)
        for name, payload in (
            ("factor_snapshot", result.factors),
            ("price_snapshot", result.history),
            ("returns", result.returns),
            ("alignment", result.sample),
            ("analysis", result.comparison),
            ("rolling", result.rolling),
            ("quality", result.quality),
        ):
            _json(directory / f"{name}.json", payload)
        _csv(
            directory / "aligned.csv",
            [
                {
                    "period": r.period,
                    "start": r.start,
                    "stock_return": r.stock_return,
                    "RF": r.rf,
                    "excess_return": r.excess_return,
                    **dict(zip(FACTOR_NAMES, r.factors, strict=True)),
                    "available_at": r.available_at.isoformat(),
                }
                for r in result.sample.rows
            ],
            [
                "period",
                "start",
                "stock_return",
                "RF",
                "excess_return",
                *FACTOR_NAMES,
                "available_at",
            ],
        )
        coefficients = []
        if result.comparison:
            for model, fit in result.comparison["fits"].items():
                for name, values in fit["coefficients"].items():
                    coefficients.append({"model": model, "term": name, **values})
        _csv(
            directory / "coefficients.csv",
            coefficients,
            [
                "model",
                "term",
                "estimate",
                "std_error",
                "t_statistic",
                "p_value",
                "ci_lower",
                "ci_upper",
            ],
        )
        rolling_rows = []
        for row in result.rolling:
            for name in ("Alpha", *FACTOR_NAMES):
                value = (
                    row.get("comparison", {})
                    .get("fits", {})
                    .get("FF4", {})
                    .get("coefficients", {})
                    .get(name, {})
                )
                rolling_rows.append(
                    {
                        "window_start": row["window_start"],
                        "window_end": row["window_end"],
                        "nobs": row["nobs"],
                        "status": row["status"],
                        "term": name,
                        "estimate": value.get("estimate"),
                        "reason": row.get("reason", ""),
                    }
                )
        _csv(
            directory / "rolling.csv",
            rolling_rows,
            ["window_start", "window_end", "nobs", "status", "term", "estimate", "reason"],
        )
        _charts(result, directory)
        limitations = list(result.warnings)
        if result.comparison:
            limitations.extend(
                w for fit in result.comparison["fits"].values() for w in fit["warnings"]
            )
        report = render_factor_report(
            {
                "config": result.config.snapshot(),
                "alignment": jsonable(result.sample),
                "analysis": result.comparison,
                "rolling": jsonable(result.rolling),
                "factor_snapshot": jsonable(result.factors),
                "price_snapshot": jsonable(result.history),
                "returns": jsonable(result.returns),
                "quality": jsonable(result.quality),
                "warnings": result.warnings,
            },
            run_id,
            generated_at,
        )
        with (directory / "report.html").open("x", encoding="utf-8") as stream:
            stream.write(report)
        provenance = collect_provenance()
        provenance["runtime_dependencies"] = {
            name: version(name) for name in ("numpy", "scipy", "statsmodels", "matplotlib")
        }
        manifest = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.iterdir()
            if p.is_file()
        }
        _json(
            directory / "run.json",
            {
                "schema_version": 3,
                "phase": 3,
                "run_id": run_id,
                "status": result.status,
                "generated_at": generated_at,
                "config": result.config.snapshot(),
                "config_hash": fingerprint(result.config.snapshot()),
                "provenance": provenance,
                "data_kind": result.config.expected_kind,
                "factor_hash": result.factors.snapshot_hash,
                "history_hash": result.history.snapshot_hash,
                "sample_hash": result.sample.sample_hash,
                "nobs": len(result.sample.rows),
                "rolling_summary": {
                    "windows": len(result.rolling),
                    "failed": sum(r["status"] == "failed" for r in result.rolling),
                },
                "cache_events": result.cache_events,
                "historical_signal_eligible": False,
                "historical_pit_verified": False,
                "warnings": limitations,
                "artifact_hashes": manifest,
            },
        )
    except OSError as exc:
        raise ReportError(
            "Factor report incomplete or run_id exists; inspect reserved directory."
        ) from exc
    return directory
