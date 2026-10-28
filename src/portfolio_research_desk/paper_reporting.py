"""Immutable CAD account exports, including original replay inputs and hash chain."""

import csv
import hashlib
import html
import json
import re
from pathlib import Path
from uuid import uuid4

from portfolio_research_desk.domain import fingerprint, jsonable
from portfolio_research_desk.errors import DataError, ReportError
from portfolio_research_desk.paper_store import loads, wire
from portfolio_research_desk.reporting import collect_provenance

WARNINGS = (
    "PAPER SIMULATION ONLY; no broker or real orders.",
    "Synthetic examples are software verification, not market performance evidence.",
    "Real historical PIT, membership, delistings and exchange calendars remain unverified.",
    "Raw prices only; actions must be supplied once at effective time before later trades.",
    "NAV already includes cash fees and FX costs; cumulative costs must not be subtracted again.",
    "Local/CAD P&L is cost-basis attribution, not a time-weighted strategy return or tax ledger.",
)


def write_native(path, payload):
    try:
        with Path(path).open("x", encoding="utf-8") as stream:
            json.dump(
                {"schema_version": 5, "payload": wire(payload)}, stream, indent=2, allow_nan=False
            )
    except OSError as exc:
        raise ReportError("Cannot create native paper input; files are never overwritten.") from exc


def read_native(path):
    try:
        values = json.loads(Path(path).read_text("utf-8"))
        if (
            set(values) != {"schema_version", "payload"}
            or type(values["schema_version"]) is not int
            or values["schema_version"] != 5
        ):
            raise DataError("Native paper input requires schema_version 5 and typed payload.")
        return loads(json.dumps(values["payload"]))
    except (OSError, ValueError, TypeError) as exc:
        raise DataError("Cannot read native paper input.") from exc


def write_paper_report(account, output_dir, run_id=None):
    view, events = account.audit()
    run_id = run_id or "paper-" + uuid4().hex[:12]
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)
    }
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id) or run_id.upper() in reserved:
        raise ReportError("Unsafe paper report run ID.")
    directory = Path(output_dir) / run_id
    try:
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory.mkdir(exist_ok=False)
        snapshot = {
            "phase": 5,
            "mode": "paper",
            "base_currency": "CAD",
            "credible_real_market_oos": False,
            "warnings": WARNINGS,
            "account": jsonable(view),
            "provenance": collect_provenance(),
            "plan_hashes": {k: fingerprint(v.plan) for k, v in view.plans.items()},
        }
        with (directory / "account.json").open("x", encoding="utf-8") as stream:
            json.dump(snapshot, stream, indent=2, sort_keys=True, allow_nan=False)
        with (directory / "events.json").open("x", encoding="utf-8") as stream:
            json.dump(events, stream, indent=2, allow_nan=False)
        fills = [fill for record in view.plans.values() for fill in record.fills]
        with (directory / "trades.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(
                (
                    "order_id",
                    "market",
                    "exchange",
                    "symbol",
                    "currency",
                    "side",
                    "quantity",
                    "execution_at",
                    "raw_price",
                    "fill_price",
                    "commission_local",
                    "cad_per_unit",
                    "fx_fee_cad",
                    "fx_rounding_cad",
                )
            )
            for f in fills:
                a = f.order.asset
                writer.writerow(
                    (
                        f.order.order_id,
                        a.market,
                        a.exchange,
                        a.symbol,
                        a.currency,
                        f.order.side,
                        f.order.quantity,
                        f.execution_at.isoformat(),
                        f.raw_price,
                        f.price,
                        f.commission_local,
                        f.fx_rate.cad_per_usd if f.fx_rate else 1,
                        f.conversion.fee_cad if f.conversion else 0,
                        f.conversion.rounding_cad if f.conversion else 0,
                    )
                )
        with (directory / "nav.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(("as_of", "nav_cad", "cash_cad", "cash_weight", "risk_violations"))
            writer.writerows(
                (v.as_of.isoformat(), v.nav_cad, v.cash_cad, v.cash_weight, ";".join(v.violations))
                for v in view.valuations
            )
        text = (
            "<html><head><meta charset='utf-8'><title>CAD Paper Account</title></head>"
            "<body><h1>CAD Paper Account</h1>"
        )
        text += "".join("<p>" + html.escape(w) + "</p>" for w in WARNINGS)
        text += "<pre>" + html.escape(json.dumps(snapshot, indent=2)) + "</pre></body></html>"
        (directory / "report.html").write_text(text, encoding="utf-8")
        hashes = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.iterdir())
        }
        with (directory / "run.json").open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "status": "complete",
                    "phase": 5,
                    "mode": "paper",
                    "files": hashes,
                    "event_count": view.event_count,
                    "ledger_head_hash": view.head_hash,
                },
                stream,
                indent=2,
            )
    except OSError as exc:
        raise ReportError(
            "Cannot complete paper report; no completion marker was written."
        ) from exc
    return directory
