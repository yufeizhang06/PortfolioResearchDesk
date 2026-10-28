from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

import pytest

from portfolio_research_desk.domain import AssetId
from portfolio_research_desk.errors import DataError, ExecutionError
from portfolio_research_desk.fx import FXBook, FXRate, load_fx_csv
from portfolio_research_desk.paper_domain import CADState, Costs, Holding, Quote
from portfolio_research_desk.paper_sample import example_inputs
from portfolio_research_desk.portfolio_risk import RiskLimits, value_portfolio


def test_historical_fx_never_uses_future_observation_or_future_revision():
    x = example_inputs()
    at = x["decision_at"]
    old = FXRate(at - timedelta(days=1), at - timedelta(days=1), D("1.30"), "old", True)
    revision = replace(old, available_at=at + timedelta(days=3), cad_per_usd=D(9))
    tomorrow = FXRate(at + timedelta(days=1), at + timedelta(days=1), D(8), "tomorrow", True)
    book = FXBook((old, revision, tomorrow))
    assert book.at(at) == old
    assert book.at(at + timedelta(days=2)) == tomorrow
    # On the later date, the most recent observation still wins over a revision of an older day.
    assert book.at(at + timedelta(days=4)) == tomorrow


@pytest.mark.parametrize(
    "case",
    ["missing", "stale", "duplicate", "naive", "negative", "nan", "unknown_source", "inverted"],
)
def test_invalid_or_unavailable_fx(case):
    at = example_inputs()["decision_at"]
    rate = FXRate(at, at, D("1.25"), "test", True)
    with pytest.raises(DataError):
        if case == "missing":
            FXBook().at(at)
        elif case == "stale":
            FXBook((rate,)).at(at + timedelta(days=8))
        elif case == "duplicate":
            FXBook((rate, rate))
        elif case == "naive":
            replace(rate, observed_at=at.replace(tzinfo=None))
        elif case == "negative":
            replace(rate, cad_per_usd=D(-1))
        elif case == "nan":
            replace(rate, cad_per_usd=D("NaN"))
        elif case == "unknown_source":
            replace(rate, source="")
        else:
            replace(rate, available_at=at - timedelta(seconds=1))


def test_native_fx_csv_roundtrip_and_errors(tmp_path):
    path = tmp_path / "fx.csv"
    path.write_text(
        "observed_at,available_at,cad_per_usd,source,synthetic\n"
        "2026-01-05T21:00:00+00:00,2026-01-05T21:01:00+00:00,1.234567,fixture,true\n",
        encoding="utf-8",
    )
    rate = load_fx_csv(path).rates[0]
    assert rate.cad_per_usd == D("1.234567") and rate.synthetic
    for contents in (
        "date,rate\n2026-01-05,1.2\n",
        "observed_at,available_at,cad_per_usd,source,synthetic\n",
        path.read_text().replace(",true", ",yes"),
        path.read_text().replace("1.234567", "NaN"),
    ):
        path.write_text(contents, encoding="utf-8")
        with pytest.raises(DataError):
            load_fx_csv(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_positions", 0),
        ("max_positions", True),
        ("max_position_weight", D("1.01")),
        ("cash_buffer", D(-1)),
        ("max_sector_weight", D(0)),
        ("max_turnover", D("NaN")),
        ("max_order_shares", -1),
        ("min_trade_cad", D(-1)),
        ("max_quote_age_seconds", 0),
        ("max_fx_age_seconds", True),
        ("max_price_deviation", D(2)),
    ],
)
def test_risk_configuration_rejects_invalid_values(field, value):
    with pytest.raises(DataError):
        replace(RiskLimits(), **{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("price", D(0)),
        ("price", D("Infinity")),
        ("price", D("10.001")),
        ("adjusted", True),
        ("volume", -1),
        ("tradable", 1),
        ("synthetic", "true"),
        ("kind", "midpoint"),
    ],
)
def test_raw_quote_contract(field, value):
    q = example_inputs()["market"].quotes[0]
    with pytest.raises(DataError):
        replace(q, **{field: value})


@pytest.mark.parametrize(
    "case",
    [
        "missing_fx",
        "missing_mark",
        "late_mark",
        "stale_mark",
        "future_state",
        "missing_sector",
        "late_sector",
    ],
)
def test_valuation_fails_without_time_correct_inputs(case):
    x = example_inputs()
    at = x["decision_at"]
    m = x["market"]
    a = m.quotes[0].asset
    state = CADState(at, positions=(Holding(a, 1, D(10), D("13.5")),))
    if case == "missing_fx":
        m = replace(m, fx=FXBook())
    if case == "missing_mark":
        m = replace(m, quotes=())
    if case == "late_mark":
        m = replace(m, quotes=(replace(m.quotes[0], available_at=at + timedelta(seconds=1)),))
    if case == "stale_mark":
        at += timedelta(days=8)
    if case == "future_state":
        state = replace(state, as_of=at + timedelta(seconds=1))
    if case == "missing_sector":
        m = replace(m, sectors=())
    if case == "late_sector":
        m = replace(m, sectors=(replace(m.sectors[0], available_at=at + timedelta(seconds=1)),))
    with pytest.raises(DataError):
        value_portfolio(state, m, at, RiskLimits())


def test_risk_reports_all_concentrations_and_cash_without_mutating_state():
    x = example_inputs()
    at = x["decision_at"]
    m = x["market"]
    state = CADState(at, positions=tuple(Holding(q.asset, 1, q.price, q.price) for q in m.quotes))
    result = value_portfolio(
        state,
        m,
        at,
        RiskLimits(max_positions=1, max_position_weight=D(".01"), max_sector_weight=D(".01")),
    )
    assert set(result.violations) == {
        "MAX_POSITIONS",
        "MAX_POSITION_WEIGHT",
        "MAX_SECTOR_WEIGHT",
        "CASH_BUFFER",
    }
    assert result.nav_cad == D("67.25")
    assert sum((p["weight"] for p in result.positions), D(0)) == pytest.approx(D(1))


def test_cad_cash_and_cad_assets_need_no_fx_and_usd_cash_does():
    x = example_inputs()
    a = x["market"].quotes[1].asset
    at = x["decision_at"]
    state = CADState(at, (("CAD", D(100)), ("USD", D(0))), positions=(Holding(a, 1, D(20), D(20)),))
    m = replace(x["market"], quotes=(x["market"].quotes[1],), fx=FXBook())
    assert value_portfolio(state, m, at, RiskLimits()).nav_cad == 120
    with pytest.raises(DataError):
        value_portfolio(replace(state, cash=(("CAD", D(100)), ("USD", D(1)))), m, at, RiskLimits())


@pytest.mark.parametrize(
    "case",
    [
        "negative_cash",
        "unsupported_cash",
        "duplicate_holding",
        "fractional",
        "unsupported_asset",
        "bad_fee",
    ],
)
def test_state_and_cost_validation(case):
    x = example_inputs()
    at = x["decision_at"]
    a = x["market"].quotes[0].asset
    h = Holding(a, 1, D(10), D(13))
    with pytest.raises((DataError, ExecutionError)):
        if case == "negative_cash":
            CADState(at, (("CAD", D(-1)), ("USD", D(0))))
        elif case == "unsupported_cash":
            CADState(at, (("CAD", D(0)), ("EUR", D(0))))
        elif case == "duplicate_holding":
            CADState(at, positions=(h, h))
        elif case == "fractional":
            replace(h, quantity=D("1.5"))
        elif case == "bad_fee":
            Costs(fixed_fee=D("0.001"))
        else:
            Quote(AssetId("EU", "XPAR", "ABC", "EUR"), at, at, D(1))
