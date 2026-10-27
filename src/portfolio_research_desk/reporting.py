"""Immutable local run bundles: typed results, snapshots, CSV ledger and HTML."""

import csv
import hashlib
import html
import json
import platform
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from portfolio_research_desk import __version__
from portfolio_research_desk.backtest import BacktestResult
from portfolio_research_desk.domain import ZERO, fingerprint, jsonable
from portfolio_research_desk.errors import ReportError


def _write_json(path: Path, content: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(jsonable(content), stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _provenance() -> dict:
    package = Path(__file__).resolve().parent
    source_hash = hashlib.sha256()
    for path in sorted(package.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".toml", ".csv"}:
            source_hash.update(path.relative_to(package).as_posix().encode("utf-8"))
            source_hash.update(b"\0")
            source_hash.update(path.read_bytes())
    root = package.parent.parent
    lock = root / "uv.lock"
    commit, dirty = None, None
    if (root / ".git").exists():
        try:
            base = ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root)]
            revision = subprocess.run(
                [*base, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10
            )
            commit = revision.stdout.strip() if revision.returncode == 0 else None
            status = subprocess.run(
                [*base, "status", "--porcelain"], capture_output=True, text=True, timeout=10
            )
            dirty = bool(status.stdout.strip()) if status.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {
        "package_version": __version__,
        "python_version": platform.python_version(),
        "source_code_hash": source_hash.hexdigest(),
        "code_commit_hash": commit,
        "working_tree_dirty": dirty,
        "dependency_lock_hash": hashlib.sha256(lock.read_bytes()).hexdigest()
        if lock.is_file()
        else None,
        "runtime_dependencies": {},
        "random_seed": None,
        "randomness": "none",
    }


def _table(fields: list[str], rows: list[dict]) -> str:
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row[field]))}</td>" for field in fields) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def collect_provenance() -> dict:
    """Shared code/version/lock provenance for simulation and research run bundles."""
    return _provenance()


def write_report(result: BacktestResult, output_dir: Path, run_id: str | None = None) -> Path:
    """Reserve a new run directory; run.json is written last as the completion marker.

    On I/O failure, leave the incomplete directory for diagnosis and raise an
    explicit error. Existing runs and files are never overwritten.
    """
    started = datetime.now(UTC)
    run_id = run_id if run_id is not None else f"{started:%Y%m%dT%H%M%S}-{uuid4().hex[:12]}"
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)
    }
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id) or run_id.upper() in reserved:
        raise ReportError(
            "run_id must be a safe, non-reserved filename of 1-80 letters/digits/_/-."
        )
    directory = output_dir / run_id
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        directory.mkdir(exist_ok=False)
    except OSError as exc:
        raise ReportError(
            "Cannot reserve a new run directory; existing runs are never overwritten."
        ) from exc
    try:
        metadata = {
            "schema_version": 1,
            "phase": 1,
            "run_id": run_id,
            "run_started_at": started.isoformat(),
            "status": "complete",
            "config_hash": fingerprint(result.config.snapshot()),
            "data_snapshot_hash": result.data_hash,
            "result_hash": fingerprint(result),
            **_provenance(),
        }
        payload = jsonable(result)
        del payload["dataset_snapshot"]
        payload["config"] = result.config.snapshot()
        payload["metadata"] = metadata
        _write_json(directory / "config_snapshot.json", result.config.snapshot())
        _write_json(directory / "data_snapshot.json", result.dataset_snapshot)
        _write_json(directory / "result.json", payload)
        fills = []
        for fill in result.fills:
            row = jsonable(fill)
            row.update(row.pop("asset"))
            row["notional"] = str(fill.price * fill.quantity)
            fills.append(row)
        fill_fields = [
            "order_id",
            "market",
            "exchange",
            "symbol",
            "currency",
            "side",
            "quantity",
            "decision_at",
            "execution_at",
            "raw_price",
            "price",
            "notional",
            "commission",
            "slippage_cost",
        ]
        _write_csv(directory / "fills.csv", fill_fields, fills)
        orders = []
        for outcome in result.orders:
            row = jsonable(outcome.order)
            row.update(row.pop("asset"))
            row.update(
                execution_at=jsonable(outcome.execution_at),
                filled_quantity=outcome.filled_quantity,
                status=outcome.status,
                reason=outcome.reason,
            )
            orders.append(row)
        _write_csv(
            directory / "orders.csv",
            [
                "order_id",
                "market",
                "exchange",
                "symbol",
                "currency",
                "side",
                "quantity",
                "decision_at",
                "reference_price",
                "execution_at",
                "filled_quantity",
                "status",
                "reason",
            ],
            orders,
        )
        equity = []
        positions = []
        previous = result.config.initial_cash
        for point in result.equity:
            equity.append(
                {
                    "session_date": point.session_date.isoformat(),
                    "valuation_at": point.valuation_at.isoformat(),
                    "currency": "USD",
                    "cash": str(point.cash),
                    "nav": str(point.nav),
                    "position_market_value": str(
                        sum((p.market_value for p in point.positions), ZERO)
                    ),
                    "period_return": str(point.nav / previous - 1),
                    "cumulative_commission": str(point.cumulative_commission),
                    "cumulative_slippage": str(point.cumulative_slippage),
                    "cash_benchmark_nav": str(point.cash_benchmark_nav),
                }
            )
            previous = point.nav
            for position in point.positions:
                row = jsonable(position)
                row.update(row.pop("asset"))
                row["session_date"] = point.session_date.isoformat()
                positions.append(row)
        equity_fields = [
            "session_date",
            "valuation_at",
            "currency",
            "cash",
            "position_market_value",
            "nav",
            "period_return",
            "cumulative_commission",
            "cumulative_slippage",
            "cash_benchmark_nav",
        ]
        _write_csv(directory / "equity.csv", equity_fields, equity)
        _write_csv(
            directory / "positions.csv",
            [
                "session_date",
                "market",
                "exchange",
                "symbol",
                "currency",
                "quantity",
                "close",
                "market_value",
                "weight",
            ],
            positions,
        )
        metric_rows = [
            {
                "metric": key,
                "value": str(value)
                if value is not None
                else "unavailable (short synthetic sample)",
            }
            for key, value in result.metrics.items()
        ]
        warning_html = "".join(f"<li>{html.escape(warning)}</li>" for warning in result.warnings)
        content = (
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width">'
            "<title>PortfolioResearchDesk — Synthetic backtest</title><style>"
            "body{font:15px system-ui;max-width:1200px;margin:32px auto;"
            "padding:0 20px;color:#182536}"
            "table{border-collapse:collapse;width:100%;font-size:13px;margin:16px 0}"
            "td,th{border:1px solid #cdd6e0;padding:7px;text-align:left}th{background:#edf2f7}"
            ".notice{background:#fff2d6;padding:16px}code{overflow-wrap:anywhere}</style>"
            '<h1>PortfolioResearchDesk · Phase 1</h1><p class="notice">'
            "<strong>SYNTHETIC · USD ONLY.</strong> Accounting and causality verification. "
            "These results are not historical market evidence or investment advice.</p>"
            f"<p>Run: <code>{html.escape(run_id)}</code> · Generated UTC: {started.isoformat()}</p>"
            "<p>Universe: user_static / user_config · as-of: "
            f"{result.universe.as_of.isoformat()} · "
            f"Assets: {html.escape(', '.join(a.symbol for a in result.universe.assets))}</p>"
            "<h2>Method and execution</h2><p>Trailing close momentum, "
            "Top-K equal targets, integer shares. Decision: scheduled close + 2 minutes. "
            "Execution: next explicit session open, sells before buys. "
            "Requests are fixed using known closes; execution may only reduce them "
            "for cash/weight limits. No model fitting or OOS evaluation. "
            "No final liquidation; last NAV includes marked holdings.</p>"
            f"<pre>{html.escape(json.dumps(result.config.snapshot(), indent=2))}</pre>"
            "<h2>Metrics</h2>"
            + _table(["metric", "value"], metric_rows)
            + "<h2>Daily NAV / cash baseline</h2>"
            + _table(equity_fields, equity)
            + "<h2>Simulated fills</h2>"
            + _table(fill_fields, fills)
            + "<h2>Limitations and data quality</h2><ul>"
            + warning_html
            + "</ul>"
            "<h2>Reproducibility</h2><pre>" + html.escape(json.dumps(metadata, indent=2)) + "</pre>"
            "<p>See result.json for decisions, input availability times, "
            "target weights and all order outcomes. "
            "config_snapshot.json and data_snapshot.json contain the complete inputs.</p></html>"
        )
        with (directory / "report.html").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
        metadata["report_paths"] = [
            "result.json",
            "config_snapshot.json",
            "data_snapshot.json",
            "equity.csv",
            "positions.csv",
            "orders.csv",
            "fills.csv",
            "report.html",
        ]
        # Only this marker certifies that all bundle files were written successfully.
        _write_json(directory / "run.json", metadata)
    except OSError as exc:
        raise ReportError(
            "Incomplete run bundle; no completion marker written. See the reserved directory."
        ) from exc
    return directory
