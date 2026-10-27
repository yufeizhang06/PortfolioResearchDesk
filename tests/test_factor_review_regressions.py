"""Counterexamples from the independent Phase 3 review; no live data required."""

import calendar
import math
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal as D
from decimal import Inexact, Rounded, localcontext
from importlib.resources import files
from pathlib import Path

import numpy as np
import pytest

from portfolio_research_desk.cli import main
from portfolio_research_desk.data_adapters import LocalHistoryAdapter, write_history
from portfolio_research_desk.domain import fingerprint, jsonable
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.factor_analysis import rolling_exposures
from portfolio_research_desk.factor_data import (
    BASE_URL,
    FactorData,
    FactorRow,
    FrenchAdapter,
    combine_factors,
    parse_french_table,
)
from portfolio_research_desk.factor_returns import (
    ReturnData,
    ReturnRow,
    align_common_sample,
    calculate_returns,
)

STAMP = datetime(2024, 6, 1, tzinfo=UTC)


def month_end(year, month):
    return date(year, month, calendar.monthrange(year, month)[1])


@pytest.fixture
def bundled():
    resource = files("portfolio_research_desk").joinpath("resources")
    history = LocalHistoryAdapter(Path(str(resource.joinpath("factor_prices.csv")))).read()
    factors = combine_factors(
        resource.joinpath("factors_ff3.csv").read_bytes(),
        resource.joinpath("factors_mom.csv").read_bytes(),
        "daily",
        STAMP,
        "synthetic",
        True,
    )
    return history, factors


def observation(template, day, price):
    event = datetime(day.year, day.month, day.day, 22, tzinfo=UTC)
    return replace(
        template,
        session_date=day,
        event_time=event,
        observation_end=event,
        open=price,
        high=price,
        low=price,
        close=price,
        adj_close=price,
    )


def monthly_inputs(template):
    dates = [month_end(2021, 12)] + [month_end(y, m) for y in (2022, 2023) for m in range(1, 13)]
    factors, observations = [], []
    price = D(100)
    for index, day in enumerate(dates):
        x = tuple(
            D(str(v))
            for v in (
                0.02 * math.sin(0.81 * index),
                0.015 * math.cos(0.61 * index),
                0.019 * math.sin(0.43 * index),
                0.017 * math.cos(0.31 * index),
            )
        )
        if index:
            betas = (D("1.5") if index == 1 else D(".7"), D("-.4"), D(".3"), D(".2"))
            price *= (
                1
                + D(".003")
                + sum(a * b for a, b in zip(x, betas, strict=True))
                + D(str(0.0003 * math.sin(index * 1.3)))
            )
            factors.append(FactorRow(day, *x[:3], D(".001"), x[3]))
        observations.append(observation(template.rows[0], day, price))
    missing = month_end(2022, 6)
    return (
        replace(template, rows=tuple(r for r in observations if r.session_date != missing)),
        FactorData(
            "monthly",
            tuple(r for r in factors if r.period != missing),
            "synthetic",
            STAMP,
            {},
            True,
        ),
        tuple(dates),
    )


def test_r1_missing_month_in_both_sources_keeps_nominal_windows(bundled):
    history, factors, sessions = monthly_inputs(bundled[0])
    returns = calculate_returns(history, factors, sessions=sessions)
    sample = align_common_sample(returns, factors, date(2022, 1, 1), date(2024, 1, 1))
    windows = rolling_exposures(sample, window=12, min_obs=6)
    assert len(windows) == 13
    assert windows[0]["window_start"] == "2022-01-31"
    assert windows[0]["window_end"] == "2022-12-31"
    january = next(r for r in windows if r["window_end"] == "2023-01-31")
    assert january["window_start"] == "2022-02-28"
    assert january["nobs"] == 10
    expected = [r for r in sample.rows if date(2022, 2, 28) <= r.period <= date(2023, 1, 31)]
    x = np.array([[1, *r.factors] for r in expected])
    y = np.array([r.excess_return for r in expected])
    q, r = np.linalg.qr(x, mode="reduced")
    beta = np.linalg.solve(r, q.T @ y)
    actual = [v["estimate"] for v in january["comparison"]["fits"]["FF4"]["coefficients"].values()]
    np.testing.assert_allclose(actual, beta, rtol=1e-10, atol=1e-12)


def test_r2_calendar_cannot_replace_existing_month_end_quote(bundled):
    history, _ = bundled
    days = [date(2023, 12, 29), date(2024, 1, 30), date(2024, 1, 31), date(2024, 2, 29)]
    history = replace(
        history,
        rows=tuple(
            observation(history.rows[0], day, D(price))
            for day, price in zip(days, (100, 105, 110, 121), strict=True)
        ),
    )
    factors = FactorData(
        "monthly",
        tuple(
            FactorRow(day, D(".01"), D(".02"), D(".03"), D(".001"), D(".04"))
            for day in (days[2], days[3])
        ),
        "synthetic",
        STAMP,
        {},
        True,
    )
    valid = calculate_returns(history, factors, sessions=tuple(days))
    assert [row.value for row in valid.rows] == [D(".1"), D(".1")]
    with pytest.raises(DataError, match="CALENDAR_PRICE_CONFLICT"):
        calculate_returns(history, factors, sessions=(days[0], days[1], days[3]))


def test_r3_provider_adjusted_close_cannot_be_labelled_price_only(bundled):
    history, factors = bundled
    adjusted = replace(
        history,
        price_basis="provider_adjusted",
        rows=tuple(observation(row, row.session_date, D(99)) for row in history.rows[:2]),
    )
    # Raw prices 100 -> 99 plus dividend 1 imply 0 total return; adjusted closes are 99 -> 99.
    assert calculate_returns(adjusted, factors, "adjusted_close").rows[0].value == 0
    with pytest.raises(DataError, match="PRICE_BASIS_CONFLICT"):
        calculate_returns(adjusted, factors, "close")


def test_r4_percent_normalization_is_independent_of_decimal_context():
    raw = b",Mkt-RF,SMB,HML,RF\n20240102,1.25,-0.5,0,0.02\n"
    expected = (D(".0125"), D("-.005"), D(0), D(".0002"))
    for precision in (2, 6, 28):
        with localcontext() as context:
            context.prec = precision
            assert parse_french_table(raw, "daily")[date(2024, 1, 2)] == expected


def test_r1_month_grid_includes_missing_leading_and_trailing_periods(bundled):
    history, factors, sessions = monthly_inputs(bundled[0])
    sample = align_common_sample(
        calculate_returns(history, factors, sessions=sessions),
        factors,
        date(2021, 12, 1),
        date(2024, 2, 1),
    )
    missing = {e["period"]: e["reason"] for e in sample.exclusions}
    assert missing["2021-12-31"] == "MISSING_STOCK_AND_FACTOR"
    assert missing["2022-06-30"] == "MISSING_STOCK_AND_FACTOR"
    assert missing["2024-01-31"] == "MISSING_STOCK_AND_FACTOR"
    windows = rolling_exposures(sample, 12, min_obs=6)
    assert len(windows) == 15
    assert windows[0]["window_end"] == "2022-11-30"
    assert windows[-1]["window_end"] == "2024-01-31"


def test_r1_rolling_also_repairs_a_legacy_sample_missing_month_exclusion(bundled):
    history, factors, sessions = monthly_inputs(bundled[0])
    sample = align_common_sample(
        calculate_returns(history, factors, sessions=sessions),
        factors,
        date(2022, 1, 1),
        date(2024, 1, 1),
    )
    legacy = replace(
        sample, exclusions=tuple(e for e in sample.exclusions if e["period"] != "2022-06-30")
    )
    windows = rolling_exposures(legacy, 12, min_obs=6)
    assert len(windows) == 13
    assert windows[1]["window_start"] == "2022-02-28"
    assert windows[1]["nobs"] == 10


def test_r1_future_changes_leave_past_monthly_windows_unchanged(bundled):
    history, factors, sessions = monthly_inputs(bundled[0])

    def run(data, factor_data):
        aligned = align_common_sample(
            calculate_returns(data, factor_data, sessions=sessions),
            factor_data,
            date(2022, 1, 1),
            date(2024, 1, 1),
        )
        return rolling_exposures(aligned, 12, min_obs=6)

    cutoff = date(2023, 6, 30)
    changed_history = replace(
        history,
        rows=tuple(
            replace(r, adj_close=r.adj_close * D("1.03")) if r.session_date > cutoff else r
            for r in history.rows
        ),
    )
    changed_factors = replace(
        factors,
        rows=tuple(
            replace(r, mkt_rf=r.mkt_rf * 2) if r.period > cutoff else r for r in factors.rows
        ),
    )
    original = [w for w in run(history, factors) if w["window_end"] <= str(cutoff)]
    changed = [w for w in run(changed_history, changed_factors) if w["window_end"] <= str(cutoff)]
    assert len(original) == 7 and original == changed


@pytest.mark.parametrize(
    "missing", [(date(2024, 1, 30),), (date(2024, 1, 31),), (date(2024, 1, 30), date(2024, 1, 31))]
)
def test_r2_calendar_conflicts_include_intermediate_dates_and_whole_months(bundled, missing):
    history, _ = bundled
    days = (date(2023, 12, 29), date(2024, 1, 30), date(2024, 1, 31), date(2024, 2, 29))
    history = replace(
        history,
        rows=tuple(
            observation(history.rows[0], d, D(v))
            for d, v in zip(days, (100, 105, 110, 121), strict=True)
        ),
    )
    factors = FactorData(
        "monthly",
        (FactorRow(days[-1], D(".01"), D(".02"), D(".03"), D(0), D(".04")),),
        "synthetic",
        STAMP,
        {},
        True,
    )
    with pytest.raises(DataError, match="CALENDAR_PRICE_CONFLICT"):
        calculate_returns(history, factors, sessions=tuple(d for d in days if d not in missing))


@pytest.mark.parametrize("calendar_kind", ["duplicate", "reversed", "empty", "timestamp"])
def test_r2_rejects_invalid_session_dates(bundled, calendar_kind):
    history, _ = bundled
    factors = FactorData(
        "monthly",
        (FactorRow(date(2024, 1, 31), D(0), D(0), D(0), D(0), D(0)),),
        "synthetic",
        STAMP,
        {},
        True,
    )
    sessions = {
        "duplicate": (date(2024, 1, 1), date(2024, 1, 1)),
        "reversed": (date(2024, 1, 2), date(2024, 1, 1)),
        "empty": (),
        "timestamp": (datetime(2024, 1, 1, tzinfo=UTC),),
    }[calendar_kind]
    with pytest.raises(DataError, match="session calendar"):
        calculate_returns(history, factors, sessions=sessions)


@pytest.mark.parametrize("bad_endpoint", ["duplicate", "unavailable"])
def test_r2_invalid_month_end_never_falls_back_to_previous_quote(bundled, bad_endpoint):
    history, _ = bundled
    days = (date(2023, 12, 29), date(2024, 1, 30), date(2024, 1, 31), date(2024, 2, 29))
    rows = tuple(
        observation(history.rows[0], d, D(v))
        for d, v in zip(days, (100, 105, 110, 121), strict=True)
    )
    if bad_endpoint == "duplicate":
        rows = (*rows, rows[2])
    else:
        rows = tuple(
            replace(r, available_at=datetime(2024, 1, 31, 21, tzinfo=UTC)) if i == 2 else r
            for i, r in enumerate(rows)
        )
    history = replace(history, rows=rows)
    factors = FactorData(
        "monthly",
        tuple(FactorRow(d, D(0), D(0), D(0), D(0), D(0)) for d in (days[2], days[3])),
        "synthetic",
        STAMP,
        {},
        True,
    )
    assert calculate_returns(history, factors, sessions=days).rows == ()


def test_monthly_interval_misalignment_is_excluded(bundled):
    history, _, _ = monthly_inputs(bundled[0])
    asset = history.rows[0].asset
    row = ReturnRow(date(2024, 2, 29), date(2023, 12, 29), D(".1"), STAMP)
    returns = ReturnData(asset, "monthly", (row,), "close", "synthetic", ())
    factors = FactorData(
        "monthly",
        (FactorRow(row.period, D(0), D(0), D(0), D(0), D(0)),),
        "synthetic",
        STAMP,
        {},
        True,
    )
    sample = align_common_sample(returns, factors, date(2024, 2, 1), date(2024, 3, 1))
    assert sample.rows == ()
    assert sample.exclusions == ({"period": "2024-02-29", "reason": "RETURN_INTERVAL_MISMATCH"},)


@pytest.mark.parametrize("price_basis", ["synthetic_raw", "raw_declared"])
def test_r3_explicit_unadjusted_and_adjusted_returns_keep_distinct_meanings(bundled, price_basis):
    history, factors = bundled
    left = replace(
        observation(history.rows[0], history.rows[0].session_date, D(100)), adj_close=D(99)
    )
    right = observation(history.rows[1], history.rows[1].session_date, D(99))
    history = replace(history, price_basis=price_basis, rows=(left, right))
    raw = calculate_returns(history, factors, "close")
    adjusted = calculate_returns(history, factors, "adjusted_close")
    assert raw.rows[0].value == D("-.01") and adjusted.rows[0].value == 0
    assert any("unadjusted" in w for w in raw.warnings)


def test_r3_provider_ohlc_retains_its_uncertainty_in_the_report_labels(bundled):
    history, factors = bundled
    result = calculate_returns(replace(history, price_basis="provider_ohlc"), factors, "close")
    assert any("adjustment conventions remain unverified" in w for w in result.warnings)
    assert not any("PRICE returns excluding dividends" in w for w in result.warnings)


def test_r3_missing_adjusted_price_never_uses_close_as_a_fallback(bundled):
    history, factors = bundled
    history = replace(
        history,
        price_basis="provider_adjusted",
        rows=tuple(replace(r, adj_close=None) for r in history.rows[:2]),
    )
    assert calculate_returns(history, factors, "adjusted_close").rows == ()


@pytest.mark.parametrize("frequency,date_text", [("daily", "20240102"), ("monthly", "202401")])
def test_r4_exact_scaling_respects_missing_values_and_ignores_context_limits(frequency, date_text):
    raw = (
        ",Mkt-RF,SMB,HML,RF\n" + date_text + ",12345.67890123456789,-0.000000012345,-99.99,\n"
    ).encode()
    expected = (D("123.4567890123456789"), D("-0.00000000012345"), None, None)
    with localcontext() as context:
        context.prec = 2
        context.Emin, context.Emax = -2, 2
        context.traps[Inexact] = context.traps[Rounded] = True
        # Measure this parse, not sticky flags left by earlier Decimal operations.
        context.clear_flags()
        result = parse_french_table(raw, frequency)
        assert list(result.values()) == [expected]
        assert not context.flags[Inexact] and not context.flags[Rounded]


def test_r4_parser_preserves_preexisting_context_flags():
    raw = b",Mkt-RF,SMB,HML,RF\n20240102,1.25,-0.5,0,0.02\n"
    with localcontext() as context:
        context.prec = 2
        context.flags[Inexact] = context.flags[Rounded] = True
        before = dict(context.flags)
        assert parse_french_table(raw, "daily")[date(2024, 1, 2)][0] == D(".0125")
        assert dict(context.flags) == before


def test_r4_factor_snapshot_is_identical_across_decimal_contexts():
    ff3 = b",Mkt-RF,SMB,HML,RF\n20240102,1.25,-0.5,0,0.02\n"
    mom = b",Mom\n20240102,2.55\n"
    expected = combine_factors(ff3, mom, "daily", STAMP, "synthetic", True)
    with localcontext() as context:
        context.prec = 2
        actual = combine_factors(ff3, mom, "daily", STAMP, "synthetic", True)
    assert actual == expected and actual.snapshot_hash == expected.snapshot_hash


def test_r4_legacy_precision_dependent_cache_cannot_be_reused(tmp_path):
    ff3 = b",Mkt-RF,SMB,HML,RF\n20240102,1.25,-0.5,0,0.02\n"
    mom = b",Mom\n20240102,2.55\n"
    calls = []

    def transport(url, timeout):
        calls.append(url)
        return mom if "Momentum" in url else ff3

    adapter = FrenchAdapter(tmp_path, transport, lambda: STAMP)
    urls = [
        BASE_URL + name + "_daily_CSV.zip"
        for name in ("F-F_Research_Data_Factors", "F-F_Momentum_Factor")
    ]
    old = combine_factors(ff3, mom, "daily", STAMP, " | ".join(urls))
    old = replace(old, rows=(replace(old.rows[0], mkt_rf=D(".012")),))
    key = fingerprint({"adapter": "french_us_v1", "urls": urls})
    adapter.cache.put(key, "real", jsonable(old), STAMP)
    with pytest.raises(DataError, match="Offline"):
        adapter.fetch(offline=True)
    assert calls == []
    actual, event = adapter.fetch()
    assert not event["hit"] and actual.rows[0].mkt_rf == D(".0125")
    with localcontext() as context:
        context.prec = 2
        cached, event = adapter.fetch(offline=True)
    assert event["hit"] and cached == actual and len(calls) == 2


@pytest.mark.parametrize(
    "issue,code", [("calendar", "CALENDAR_PRICE_CONFLICT"), ("price_basis", "PRICE_BASIS_CONFLICT")]
)
def test_review_input_conflicts_exit_2_without_success_bundle(
    bundled, tmp_path, capsys, issue, code
):
    history, _ = bundled
    if issue == "calendar":
        days = (date(2023, 12, 29), date(2024, 1, 30), date(2024, 1, 31), date(2024, 2, 29))
        history = replace(
            history,
            rows=tuple(
                observation(history.rows[0], day, D(value))
                for day, value in zip(days, (100, 105, 110, 121), strict=True)
            ),
        )
        (tmp_path / "ff3.csv").write_text(
            ",Mkt-RF,SMB,HML,RF\n202401,1,2,3,.1\n202402,2,3,4,.1\n", encoding="utf-8"
        )
        (tmp_path / "mom.csv").write_text(",Mom\n202401,1\n202402,2\n", encoding="utf-8")
        (tmp_path / "sessions.txt").write_text(
            "2023-12-29\n2024-01-30\n2024-02-29\n", encoding="utf-8"
        )
        specific = (
            'frequency="monthly"\nfactor_source="local"\nff3_file="ff3.csv"\n'
            'momentum_file="mom.csv"\nsessions_file="sessions.txt"\n'
        )
    else:
        history = replace(history, price_basis="provider_adjusted")
        specific = 'frequency="daily"\nfactor_source="synthetic"\nreturn_basis="close"\n'
    write_history(history, tmp_path / "prices.csv")
    config = tmp_path / "config.toml"
    config.write_text(
        'schema_version=3\nexpected_kind="synthetic"\nprice_file="prices.csv"\n'
        'start="2024-01-01"\nend="2024-03-01"\nmin_obs=6\nrolling_window=6\n' + specific,
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as error:
        main(
            [
                "research",
                "run",
                "--config",
                str(config),
                "--output-dir",
                str(tmp_path / "reports"),
                "--run-id",
                "rejected",
            ]
        )
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == "" and code in output.err
    assert not (tmp_path / "reports" / "rejected" / "run.json").exists()
