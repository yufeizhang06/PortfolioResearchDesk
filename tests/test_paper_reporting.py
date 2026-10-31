"""Presentation regressions against actual ledger/audit outputs, without network or clocks."""

import csv
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, localcontext
from decimal import Decimal as D
from html.parser import HTMLParser

import pytest

from portfolio_research_desk.domain import fingerprint, jsonable
from portfolio_research_desk.fx import FXBook, FXRate
from portfolio_research_desk.paper_report_html import render_account_report
from portfolio_research_desk.paper_reporting import write_paper_report
from portfolio_research_desk.paper_sample import example_inputs
from portfolio_research_desk.paper_store import PaperAccount
from portfolio_research_desk.portfolio_risk import MarketSnapshot
from portfolio_research_desk.product_workflow import run_workflow
from portfolio_research_desk.workflow_config import WorkflowConfig

GENERATED = datetime(2026, 10, 29, 6, 0, tzinfo=UTC)


class Report(HTMLParser):
    """Read rendered cell/metric text, rather than checking hidden source strings."""

    def __init__(self, source):
        super().__init__()
        self.tables, self.metrics, self.downloads = {}, {}, []
        self.table_id = self.metric_id = self.cell = None
        self.row = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.table_id = attrs["id"]
            self.tables[self.table_id] = []
        if tag == "tr":
            self.row = []
        if tag == "td":
            self.cell = ""
        if tag == "small" and self.cell is not None:
            self.cell += " | "
        if tag == "strong" and "id" in attrs:
            self.metric_id = attrs["id"]
            self.metrics[self.metric_id] = ""
        if tag == "a" and "download" in attrs:
            self.downloads.append(attrs["href"])

    def handle_data(self, value):
        if self.cell is not None:
            self.cell += value
        if self.metric_id:
            self.metrics[self.metric_id] += value

    def handle_endtag(self, tag):
        if tag == "td":
            self.row.append(self.cell)
            self.cell = None
        if tag == "tr" and self.row:
            self.tables[self.table_id].append(self.row)
        if tag == "table":
            self.table_id = None
        if tag == "strong":
            self.metric_id = None


def amount(value, currency="CAD"):
    # Independent decimal rounding reference, not the production formatter.
    with localcontext() as context:
        context.prec = 80
        v = D(value).quantize(D(".01"), rounding=ROUND_HALF_UP)
        return f"{currency} {v:,.2f}"


def pct(value):
    with localcontext() as context:
        context.prec = 80
        return f"{(D(value) * 100).quantize(D('.01'), rounding=ROUND_HALF_UP):,.2f}%"


def executed(tmp_path):
    x = example_inputs()
    account = PaperAccount.create(tmp_path / "account.sqlite3", x["sessions"][0].open_at)
    view = account.propose(x["bundle"], x["market"], x["sessions"], x["decision_at"], "demo")
    account.review("demo", x["review_at"], fingerprint(view.plans["demo"].plan), True, "Fixture")
    account.execute("demo", x["execution_at"], x["execution_market"])
    return account, x


def export(account, tmp_path, run="report"):
    directory = write_paper_report(account, tmp_path, run, generated_at=GENERATED)
    source = (directory / "report.html").read_text("utf-8")
    return directory, source, Report(source)


def test_existing_workflow_fixture_visible_values_reconcile_to_raw_exports(tmp_path):
    result = run_workflow(WorkflowConfig(output_dir=tmp_path), "workflow")
    account = PaperAccount(tmp_path / "workflow/account.sqlite3")
    before = account.path.read_bytes()
    view, events = account.audit()
    directory, source, parsed = export(account, tmp_path)
    raw = json.loads((directory / "account.json").read_text("utf-8"))
    assert raw["account"] == jsonable(view)
    assert json.loads((directory / "events.json").read_text("utf-8")) == list(events)
    assert account.path.read_bytes() == before
    assert raw["report_generated_at"] == GENERATED.isoformat()
    assert result  # The regular workflow also uses the new report writer.
    v = raw["account"]["valuations"][-1]
    state = raw["account"]["state"]
    assert parsed.metrics == {
        "nav": amount(v["nav_cad"]),
        "cash": amount(v["cash_cad"]),
        "holdings-value": amount(sum(D(p["value_cad"]) for p in v["positions"])),
        "pnl": amount(D(v["nav_cad"]) - D(state["net_contributions_cad"])),
    }
    assert parsed.metrics["nav"] == "CAD 2,971.17"
    assert parsed.metrics["pnl"] == "CAD -28.83"
    for row, p in zip(parsed.tables["holdings"], v["positions"], strict=True):
        assert p["asset"]["symbol"] in row[0]
        assert p["asset"]["exchange"] in row[0]
        assert row[1:] == [
            f"{p['quantity']:,}",
            amount(p["price_local"], p["asset"]["currency"]),
            amount(p["value_cad"]),
            pct(p["weight"]),
            amount(p["cad_pnl"]) + " | " + pct(p["cad_cost_return"]),
        ]
    with (directory / "trades.csv").open(newline="") as stream:
        trades = sorted(csv.DictReader(stream), key=lambda t: (t["execution_at"], t["order_id"]))
    for row, t in zip(parsed.tables["trades"], trades, strict=True):
        assert t["symbol"] in row[1] and t["exchange"] in row[1]
        assert row[2] == f"{t['side']} | {int(t['quantity']):,} shares"
        assert row[3:] == [
            amount(t["fill_price"], t["currency"]),
            amount(t["commission_local"], t["currency"]),
            f"{D(t['cad_per_unit']):,.6f}",
            amount(t["fx_fee_cad"]),
        ]
    for row, key in zip(
        parsed.tables["costs"],
        ("commission_cad", "fx_cost_cad", "slippage_cad", "realized_pnl_cad", "dividends_cad"),
        strict=True,
    ):
        assert row[1] == amount(state[key])
    with (directory / "nav.csv").open(newline="") as stream:
        assert list(csv.DictReader(stream))[-1]["nav_cad"] == v["nav_cad"]
    assert "<pre" not in source and "<script" not in source
    assert "0.79698233355883372543476139029405924265525028860685" not in source
    assert "@page { size:A4 portrait" in source
    assert source.index("Portfolio Overview") < source.index("Trading History")
    assert source.index("Trading History") < source.index("Data &amp; Methodology")
    assert set(parsed.downloads) == {
        "account.json",
        "events.json",
        "trades.csv",
        "nav.csv",
        "run.json",
    }
    manifest = json.loads((directory / "run.json").read_text())
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("kind", ["CASH", "CONVERT", "ACTION"])
def test_economic_changes_hide_old_nav_and_never_mix_state_clocks(tmp_path, kind):
    account, x = executed(tmp_path)
    at = x["execution_at"]
    command = dict(kind=kind, at=at, fx=x["execution_market"].fx)
    if kind == "CASH":
        command.update(currency="CAD", amount=D("100.00"))
    elif kind == "CONVERT":
        command.update(source="CAD", amount=D("10.00"))
    else:
        command.update(
            at=at + timedelta(seconds=1),
            asset=x["bundle"].universe.assets[0],
            action="SPLIT",
            amount=D(2),
            available_at=at,
        )
    view = account.append("change", command)
    _, source, parsed = export(account, tmp_path)
    assert "Last recorded NAV was CAD 2,994.48" in source
    assert set(parsed.metrics.values()) == {"Not available"}
    assert "Valuation required" in source
    assert "Not assessed" in source and "No recorded concentration" not in source
    assert [r[1] for r in parsed.tables["holdings"]] == [
        f"{p.quantity:,}" for p in view.state.positions
    ]
    assert all(r[2] == "Not valued" for r in parsed.tables["holdings"])


def test_unvalued_pending_and_rejected_plans_are_not_fills(tmp_path):
    x = example_inputs()
    account = PaperAccount.create(tmp_path / "account.sqlite3", x["sessions"][0].open_at)
    view = account.propose(x["bundle"], x["market"], x["sessions"], x["decision_at"], "pending")
    _, source, parsed = export(account, tmp_path)
    assert "PENDING_REVIEW" in source and "No simulated fills" in source
    assert "No current holdings" in source and "Valuation required" in source
    assert set(parsed.metrics.values()) == {"Not available"}
    account.review(
        "pending",
        x["review_at"],
        fingerprint(view.plans["pending"].plan),
        False,
        "<script>unsafe & rejected</script>",
    )
    _, source, _ = export(account, tmp_path, "rejected")
    assert "REJECTED" in source and "No simulated fills" in source
    assert "&lt;script&gt;unsafe &amp; rejected&lt;/script&gt;" in source
    assert "<script>" not in source


@pytest.mark.parametrize("zero", [False, True])
def test_cash_only_and_zero_nav_do_not_invent_allocation(zero, tmp_path):
    at = example_inputs()["execution_at"]
    account = PaperAccount.create(tmp_path / "account.sqlite3", at)
    if zero:
        account.append(
            "withdraw", dict(kind="CASH", at=at, currency="CAD", amount=D("-3000.00"), fx=FXBook())
        )
    account.append("value", dict(kind="VALUE", at=at, market=MarketSnapshot(())))
    _, source, parsed = export(account, tmp_path)
    assert parsed.metrics["nav"] == ("CAD 0.00" if zero else "CAD 3,000.00")
    assert parsed.metrics["pnl"] == "CAD 0.00"
    assert "No current holdings" in source
    assert ("Allocation unavailable" in source) is zero
    assert ("100.00% in cash" in source) is not zero


def test_recorded_violations_and_distinct_input_clocks_are_visible(tmp_path):
    account, x = executed(tmp_path)
    at = x["sessions"][1].close_at
    observed, available = at - timedelta(minutes=2), at - timedelta(minutes=1)
    market = replace(
        x["execution_market"],
        quotes=tuple(
            replace(
                q,
                price=D("500.00") if i == 0 else q.price,
                observed_at=observed,
                available_at=available,
                kind="close",
            )
            for i, q in enumerate(x["execution_market"].quotes)
        ),
        fx=FXBook((FXRate(observed, available, D("1.30"), "fx <source>", True),)),
    )
    view = account.append("value", dict(kind="VALUE", at=at, market=market))
    _, source, parsed = export(account, tmp_path)
    assert "MAX_POSITION_WEIGHT" in source and "MAX_SECTOR_WEIGHT" in source
    assert parsed.tables["risk"][0][-1] == "BREACH"
    assert parsed.tables["risk"][0][1] == pct(
        max(p["weight"] for p in view.valuations[-1].positions)
    )
    for timestamp in (
        "2026-10-29 06:00:00 UTC",
        "2026-01-06 21:00:00 UTC",
        "2026-01-06 20:58:00 UTC",
        "2026-01-06 20:59:00 UTC",
    ):
        assert timestamp in source
    assert "fx &lt;source&gt;" in source
    assert "No recorded concentration" not in source


@pytest.mark.parametrize(
    "flags,expected",
    [
        ((True, True, True), "SYNTHETIC VALUATION"),
        ((False, False, False), "OBSERVED INPUTS / UNVERIFIED"),
        ((True, False, True), "MIXED INPUTS"),
    ],
)
def test_input_classification_is_derived_not_hardcoded(tmp_path, flags, expected):
    account, x = executed(tmp_path)
    at = x["sessions"][1].close_at
    market = replace(
        x["execution_market"],
        quotes=tuple(
            replace(q, synthetic=flag)
            for q, flag in zip(x["execution_market"].quotes, flags, strict=True)
        ),
        fx=FXBook(tuple(replace(r, synthetic=flags[0]) for r in x["execution_market"].fx.rates)),
    )
    account.append("value", dict(kind="VALUE", at=at, market=market))
    _, source, _ = export(account, tmp_path)
    assert expected in source
    if expected != "SYNTHETIC VALUATION":
        assert "SYNTHETIC VALUATION" not in source
    if expected == "MIXED INPUTS":
        assert (
            "this is not an entirely synthetic valuation or verified market performance.</p>"
            in source
        )


def test_standalone_fx_and_decimal_context_do_not_change_export(tmp_path):
    account, x = executed(tmp_path)
    at = x["execution_at"]
    account.append(
        "convert",
        dict(kind="CONVERT", at=at, source="CAD", amount=D("10.00"), fx=x["execution_market"].fx),
    )
    view, events = account.audit()
    normal = render_account_report(view, events, GENERATED, "context")
    with localcontext() as context:
        context.prec, context.rounding = 6, ROUND_DOWN
        assert render_account_report(view, events, GENERATED, "context") == normal
    row = Report(normal).tables["conversions"][0]
    c = view.conversions[0]
    assert row == [
        amount(c.source_amount, c.source_currency),
        amount(c.destination_amount, c.destination_currency),
        f"{c.rate.cad_per_usd:.6f}",
        amount(c.fee_cad),
        amount(c.rounding_cad),
    ]


def test_print_does_not_drop_long_histories(tmp_path):
    account, _ = executed(tmp_path)
    view, events = account.audit()
    record = view.plans["demo"]
    # A presentation-only stress fixture: never persisted or represented as market evidence.
    long_record = replace(record, fills=record.fills * 30)
    long_view = replace(view, plans={"demo": long_record})
    report = Report(render_account_report(long_view, events, GENERATED, "long"))
    assert len(report.tables["trades"]) == len(record.fills) * 30


def test_same_symbol_different_exchanges_remains_distinct(tmp_path):
    x = example_inputs()
    mapping = {a: replace(a, symbol="SAME") for a in x["bundle"].universe.assets}
    bundle = replace(
        x["bundle"],
        universe=replace(x["bundle"].universe, assets=tuple(mapping.values())),
        signals=tuple(replace(s, asset=mapping[s.asset]) for s in x["bundle"].signals),
    )

    def market(snapshot):
        return replace(
            snapshot,
            quotes=tuple(replace(q, asset=mapping[q.asset]) for q in snapshot.quotes),
            sectors=tuple(replace(s, asset=mapping[s.asset]) for s in snapshot.sectors),
        )

    account = PaperAccount.create(tmp_path / "same.sqlite3", x["sessions"][0].open_at)
    view = account.propose(bundle, market(x["market"]), x["sessions"], x["decision_at"], "same")
    account.review("same", x["review_at"], fingerprint(view.plans["same"].plan), True, "Fixture")
    account.execute("same", x["execution_at"], market(x["execution_market"]))
    _, _, parsed = export(account, tmp_path)
    assert len(parsed.tables["holdings"]) == 3
    assert len(parsed.tables["trades"]) == 3
    assert len({r[0] for r in parsed.tables["holdings"]}) == 3
    assert all("SAME" in r[0] for r in parsed.tables["holdings"])


def test_generation_timestamp_must_be_utc_before_creating_files(tmp_path):
    account, _ = executed(tmp_path)
    from portfolio_research_desk.errors import DataError

    with pytest.raises(DataError):
        write_paper_report(account, tmp_path, "bad", generated_at=datetime(2026, 1, 1))
    assert not (tmp_path / "bad").exists()
