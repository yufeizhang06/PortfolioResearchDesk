"""Reconcile visible reports with real offline engine outputs, including adverse cases."""

import json
import re
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, localcontext
from html.parser import HTMLParser

import pytest

from portfolio_research_desk.backtest import run_backtest
from portfolio_research_desk.backtest_config import BacktestConfig
from portfolio_research_desk.backtest_report_html import drawdown_series, render_backtest_report
from portfolio_research_desk.factor_config import load_factor_config
from portfolio_research_desk.factor_report_html import render_factor_report
from portfolio_research_desk.factor_reporting import save_factor_report
from portfolio_research_desk.factor_workflow import run_factor_research
from portfolio_research_desk.ml_config import MLConfig
from portfolio_research_desk.ml_report_html import MODEL_NAMES, render_ml_report
from portfolio_research_desk.ml_reporting import save_ml_report
from portfolio_research_desk.ml_workflow import run_ml_experiment
from portfolio_research_desk.report_design import line_chart, number, percent, stamp, time_range
from portfolio_research_desk.reporting import write_report

GENERATED = datetime(2026, 10, 29, 7, 0, tzinfo=UTC)


class VisibleReport(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tables, self.metrics, self.links = {}, {}, []
        self.table_id = self.metric_id = self.cell = self.row = None
        self.tags = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append(tag)
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
            self.links.append(attrs["href"])

    def handle_data(self, text):
        if self.cell is not None:
            self.cell += text
        if self.metric_id is not None:
            self.metrics[self.metric_id] += text

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


def rounded(value, places=2, pct=False, usd=False):
    """Independent display rounding oracle; do not reuse production formatters."""
    if value is None:
        return "Not available"
    with localcontext() as ctx:
        ctx.prec = 80
        value = Decimal(str(value)) * (100 if pct else 1)
        value = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        if not value:
            value = abs(value)
        return ("USD " if usd else "") + f"{value:,.{places}f}" + ("%" if pct else "")


def read(directory, name):
    return json.loads((directory / (name + ".json")).read_text("utf-8"))


def factor_data(directory):
    data = {
        k: read(directory, k)
        for k in (
            "alignment",
            "analysis",
            "rolling",
            "factor_snapshot",
            "price_snapshot",
            "returns",
            "quality",
        )
    }
    data.update(
        config=read(directory, "run")["config"], warnings=read(directory, "run")["warnings"]
    )
    return data


def ml_data(directory):
    data = {
        k: read(directory, k)
        for k in (
            "metrics",
            "folds",
            "frozen_plan",
            "portfolios",
            "cost_sensitivity",
        )
    }
    data.update(
        config=read(directory, "config_snapshot"),
        dataset=read(directory, "data_snapshot"),
        warnings=read(directory, "run")["warnings"],
    )
    return data


@pytest.fixture(scope="module")
def bundles(tmp_path_factory):
    root = tmp_path_factory.mktemp("unified-reports")
    results = {
        "factor": run_factor_research(load_factor_config()),
        "ml": run_ml_experiment(MLConfig(sessions=240, holdout_dates=20)),
        "backtest": run_backtest(BacktestConfig()),
    }
    writers = {"factor": save_factor_report, "ml": save_ml_report, "backtest": write_report}
    return {
        kind: (result, writers[kind], writers[kind](result, root, kind))
        for kind, result in results.items()
    }


@pytest.mark.parametrize("kind", ["factor", "ml", "backtest"])
def test_writers_keep_exact_audit_payloads_independent_of_html(
    bundles, tmp_path, monkeypatch, kind
):
    result, writer, directory = bundles[kind]
    before = deepcopy(result)
    module = {"factor": "factor_reporting", "ml": "ml_reporting", "backtest": "reporting"}[kind]
    marker = read(directory, "run")

    class ExportClock(datetime):
        @staticmethod
        def now(_zone):
            key = "generated_at" if kind == "factor" else "run_started_at"
            return datetime.fromisoformat(marker[key])

    monkeypatch.setattr(f"portfolio_research_desk.{module}.datetime", ExportClock)
    monkeypatch.setattr(f"portfolio_research_desk.{module}.render_{kind}_report", lambda *a: "ok")
    second = writer(result, tmp_path, kind)
    assert result == before
    names = [
        p.name
        for p in directory.iterdir()
        if p.suffix in (".json", ".csv") and p.name != "run.json"
    ]
    assert names
    for name in names:
        assert (directory / name).read_bytes() == (second / name).read_bytes(), name


@pytest.mark.parametrize("kind", ["factor", "ml", "backtest"])
def test_reports_have_real_sections_local_downloads_and_no_raw_payload(bundles, kind):
    directory = bundles[kind][2]
    source = (directory / "report.html").read_text("utf-8")
    report = VisibleReport(source)
    assert {"pre", "script", "iframe"}.isdisjoint(report.tags)
    assert all(f'id="{name}"' in source for name in ("overview", "details", "methodology"))
    assert "@page { size:A4 portrait" in source and "break-inside:avoid" in source
    assert "https://" not in source and report.links
    assert all((directory / name).is_file() for name in report.links)
    assert not re.search(r"\d\.\d{8,}", source)
    assert "Report generated" in source and "SYNTHETIC" in source
    marker = read(directory, "run")
    assert stamp(marker["generated_at"] if kind == "factor" else marker["run_started_at"]) in source


def test_factor_visible_coefficients_comparison_and_quality_reconcile(bundles):
    directory = bundles["factor"][2]
    data = factor_data(directory)
    report = VisibleReport((directory / "report.html").read_text("utf-8"))
    fits = data["analysis"]["fits"]
    assert report.metrics == {
        "factor-alpha": rounded(fits["FF4"]["coefficients"]["Alpha"]["estimate"], 4, pct=True),
        "factor-beta": rounded(fits["FF4"]["coefficients"]["Mkt-RF"]["estimate"], 3),
        "factor-r2": rounded(fits["FF4"]["r_squared"], pct=True),
        "factor-nobs": str(len(data["alignment"]["rows"])),
    }
    for row in report.tables["factor-coefficients"]:
        model, term = row[:2]
        coef = fits[model]["coefficients"][term]
        places, pct = (4, True) if term == "Alpha" else (3, False)
        p = coef["p_value"]
        assert row[2:] == [
            rounded(coef["estimate"], places, pct),
            rounded(coef["std_error"], places, pct),
            rounded(coef["t_statistic"]),
            "<0.0001" if p < 0.0001 else rounded(p, 4),
            f"{rounded(coef['ci_lower'], places, pct)} to {rounded(coef['ci_upper'], places, pct)}",
        ]
    for row in report.tables["factor-comparison"]:
        fit = fits[row[0]]
        assert row[1:] == [
            rounded(fit["r_squared"], pct=True),
            rounded(fit["adjusted_r_squared"], pct=True),
            rounded(fit["aic"]),
            rounded(fit["bic"]),
            str(fit["nobs"]),
        ]
    quality = dict(report.tables["factor-method"])["Quality / alignment"]
    assert quality == "97 accepted prices; 0 quarantined; 0 excluded alignment periods."


def test_factor_failed_analysis_and_monthly_units_remain_explicit(tmp_path, bundles):
    failed = run_factor_research(replace(load_factor_config(), end=date(2024, 1, 10)))
    directory = save_factor_report(failed, tmp_path, "failed")
    source = (directory / "report.html").read_text("utf-8")
    assert "Analysis failed" in source and "INSUFFICIENT_SAMPLE" in source
    assert VisibleReport(source).metrics["factor-alpha"] == "Not available"
    data = factor_data(bundles["factor"][2])
    data["config"]["frequency"] = "monthly"
    data["rolling"][1].update(status="failed", comparison=None, reason="rank deficient")
    monthly = render_factor_report(data, "monthly", GENERATED)
    assert "per month" in monthly and "1 failed" in monthly
    assert "per day" not in monthly


def test_ml_all_models_stages_and_portfolio_costs_reconcile(bundles):
    directory = bundles["ml"][2]
    data = ml_data(directory)
    source = (directory / "report.html").read_text("utf-8")
    report = VisibleReport(source)
    selected = data["frozen_plan"]["selected_model"]
    assert report.metrics["ml-selected"] == MODEL_NAMES[selected]
    for stage in ("development", "holdout"):
        assert len(report.tables[f"ml-{stage}"]) == len(data["metrics"][stage])
        for name, m in data["metrics"][stage].items():
            row = next(r for r in report.tables[f"ml-{stage}"] if r[0] == MODEL_NAMES[name])
            assert row[1:3] == [rounded(m["accuracy"], pct=True), rounded(m["f1"], 3)]
            assert row[3].split(" | ")[0] == rounded(m["roc_auc"], 3)
            assert row[4:] == [
                rounded(m["precision"], pct=True),
                rounded(m["recall"], pct=True),
                f"{m['nobs']} / {m['predictions']}",
                str(m["excluded"]),
            ]
    assert len(report.tables["ml-portfolios"]) == len(data["portfolios"])
    for key, value in data["portfolios"].items():
        stage, name = key.split("/")
        row = next(
            r for r in report.tables["ml-portfolios"] if r[0] == f"{stage} / {MODEL_NAMES[name]}"
        )
        m = value["metrics"]
        assert row[1:] == [
            rounded(m["ending_nav"], usd=True),
            rounded(m["cumulative_return"], pct=True),
            rounded(m["max_drawdown"], pct=True),
            rounded(m["total_commission"], usd=True),
            rounded(m["total_slippage_cost"], usd=True),
            str(m["fill_count"]),
        ]
    for stage, scenario, *values in report.tables["ml-costs"]:
        m = data["cost_sensitivity"][f"{stage}/{selected}"][scenario]
        assert values == [
            rounded(m["cumulative_return"], pct=True),
            rounded(m["total_commission"], usd=True),
            rounded(m["total_slippage_cost"], usd=True),
        ]
    available = dict(report.tables["ml-method"])["Price inputs available"]
    assert available != "Not recorded" and "2020-01-02 21:01:00 UTC" in available
    holdout = next(r["fold"] for r in data["folds"] if r["fold"]["stage"] == "holdout")
    chart = source.split('id="ml-nav"', 1)[1].split("</figure>", 1)[0]
    assert holdout["test_start"][:10] in chart and holdout["test_end"][:10] in chart
    assert "2020-01-02" not in chart


def test_ml_does_not_reselect_on_holdout_or_hide_undefined_auc(bundles):
    data = ml_data(bundles["ml"][2])
    selected = data["frozen_plan"]["selected_model"]
    challenger = next(m for m in data["metrics"]["holdout"] if m != selected)
    data["metrics"]["holdout"][challenger]["f1"] = 1
    data["metrics"]["holdout"][selected].update(roc_auc=None, auc_unavailable_reason="one class")
    source = render_ml_report(data, "edge", GENERATED)
    report = VisibleReport(source)
    assert report.metrics["ml-selected"] == MODEL_NAMES[selected]
    assert report.metrics["ml-auc"] == "Not available"
    assert "one class" in source
    assert any(r[2] == "1.000" for r in report.tables["ml-holdout"])
    data["folds"] = []
    assert "No evaluation folds recorded" in render_ml_report(data, "empty", GENERATED)


def test_backtest_cards_holdings_and_trades_reconcile(bundles):
    directory = bundles["backtest"][2]
    data = read(directory, "result")
    source = (directory / "report.html").read_text("utf-8")
    report = VisibleReport(source)
    m = data["metrics"]
    assert report.metrics == {
        "backtest-nav": rounded(m["ending_nav"], usd=True),
        "backtest-return": rounded(m["cumulative_return"], pct=True),
        "backtest-drawdown": rounded(m["max_drawdown"], pct=True),
        "backtest-benchmark": rounded(m["cash_benchmark_return"], pct=True),
    }
    for row, p in zip(
        report.tables["backtest-holdings"], data["equity"][-1]["positions"], strict=True
    ):
        assert row[1:] == [
            str(p["quantity"]),
            rounded(p["close"], usd=True),
            rounded(p["market_value"], usd=True),
            rounded(p["weight"], pct=True),
        ]
    for row, f in zip(report.tables["backtest-fills"], data["fills"], strict=True):
        assert row[2:] == [
            f["side"],
            str(f["quantity"]),
            rounded(f["price"], usd=True),
            rounded(f["commission"], usd=True),
            rounded(f["slippage_cost"], usd=True),
        ]
    assert all(r[1] == "Not available" for r in report.tables["backtest-risk"][:3])
    assert sum(o["status"] != "FILLED" for o in data["orders"]) == len(
        report.tables["backtest-exceptions"]
    )
    assert dict(report.tables["backtest-method"])["Close inputs available"] != "Not recorded"
    path = drawdown_series(data["equity"], m["initial_nav"])
    assert -min(path) == Decimal(m["max_drawdown"])
    with localcontext() as ctx:
        ctx.prec, ctx.rounding = 6, ROUND_DOWN
        assert drawdown_series(data["equity"], m["initial_nav"]) == path


def test_backtest_no_trades_or_positions_is_clear(bundles):
    directory = bundles["backtest"][2]
    data = read(directory, "result")
    data["fills"] = []
    data["equity"][-1]["positions"] = []
    source = render_backtest_report(data, read(directory, "data_snapshot"), "empty", GENERATED)
    assert "No simulated fills" in source and "No open holdings" in source
    assert "backtest-fills" not in VisibleReport(source).tables


@pytest.mark.parametrize("kind", ["factor", "ml", "backtest"])
def test_untrusted_text_escaped_and_renderer_does_not_mutate_inputs(bundles, kind):
    directory = bundles[kind][2]
    data = {"factor": factor_data, "ml": ml_data}.get(kind, lambda p: read(p, "result"))(directory)
    data["warnings"].append('<script>alert("audit")</script>')
    original = deepcopy(data)
    renderer = {
        "factor": render_factor_report,
        "ml": render_ml_report,
        "backtest": render_backtest_report,
    }[kind]
    args = [data] + ([read(directory, "data_snapshot")] if kind == "backtest" else [])
    source = renderer(*args, "<bad&run>", GENERATED)
    assert data == original
    assert "script" not in VisibleReport(source).tags
    assert "&lt;script&gt;" in source and "&lt;bad&amp;run&gt;" in source


def test_formatting_and_clocks_are_explicit_and_context_independent():
    with localcontext() as ctx:
        ctx.prec, ctx.rounding = 3, ROUND_DOWN
        assert number("1234567.895") == "1,234,567.90"
        assert percent("0.123456789") == "12.35%"
        assert number("-0.0000001") == "0.00"
    assert number(None) == number(float("nan")) == percent(None) == "Not available"
    assert stamp("2024-01-02T09:30:00-05:00") == "2024-01-02 14:30:00 UTC"
    assert time_range(["2024-01-02T15:00:00+02:00", "2024-01-02T09:30:00-05:00"]) == (
        "2024-01-02 13:00:00 UTC to 2024-01-02 14:30:00 UTC"
    )


def test_chart_gaps_single_points_and_unavailable_results():
    source = line_chart(["a", "b", "c", "d", "e"], [("A", [1, 2, None, 4, 5])], "gap", "Gap")
    paths = re.findall(r'<path d="([^"]+)" fill="none"', source)
    assert len(paths) == 2 and all(p.count("M") == 1 and p.count("L") == 1 for p in paths)
    assert "<circle " in line_chart(["a"], [("A", [0])], "one", "One")
    assert "Chart unavailable" in line_chart(["a"], [("A", [None])], "none", "None")
    with pytest.raises(ValueError, match="align"):
        line_chart(["a"], [("A", [1, 2])], "bad", "Bad")
