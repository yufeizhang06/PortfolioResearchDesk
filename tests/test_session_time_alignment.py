"""R5: daily source events must belong to the declared exchange-local session."""

import calendar
import math
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

import numpy as np
import pytest

from portfolio_research_desk import data_contracts, factor_cli
from portfolio_research_desk.cli import main
from portfolio_research_desk.data_adapters import write_history
from portfolio_research_desk.data_contracts import History, Observation, validate_quality
from portfolio_research_desk.domain import AssetId
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.factor_analysis import rolling_exposures
from portfolio_research_desk.factor_data import FactorData, FactorRow
from portfolio_research_desk.factor_returns import align_common_sample, calculate_returns
from portfolio_research_desk.factor_workflow import run_factor_research

STAMP = datetime(2025, 6, 1, tzinfo=UTC)
ASSET = AssetId("US", "XNAS", "SYN_R5", "USD")


def quote(day, value=D(100)):
    event = datetime(day.year, day.month, day.day, 21, tzinfo=UTC)
    return Observation(ASSET, day, event, event, STAMP, value, value, value, value, 100, value)


def history(rows, availability_basis="retrieved_snapshot", **kwargs):
    return History(
        "synthetic",
        "self_authored_R5",
        "synthetic_raw",
        availability_basis,
        STAMP,
        tuple(rows),
        **kwargs,
    )


def factor_data(frequency, days):
    return FactorData(
        frequency,
        tuple(FactorRow(d, D(".01"), D(".02"), D(".03"), D(".001"), D(".04")) for d in days),
        "synthetic R5",
        STAMP,
        {},
        True,
    )


@pytest.mark.parametrize("frequency", ["daily", "monthly"])
def test_r5_known_future_event_cannot_enter_factor_returns(frequency):
    days = (date(2022, 5, 31), date(2022, 6, 30), date(2022, 7, 29))
    data = history(quote(d, D(v)) for d, v in zip(days, (100, 110, 121), strict=True))
    future_quote = replace(data.rows[-1], session_date=days[1])
    data = replace(data, rows=(data.rows[0], future_quote, data.rows[-1]))
    report = validate_quality(data)
    assert future_quote in report.quarantined
    assert "SESSION_TIME_MISMATCH" in {i.code for i in report.issues}
    factors = factor_data(frequency, days if frequency == "daily" else (days[1], date(2022, 7, 31)))
    with pytest.raises(DataError, match="SESSION_TIME_MISMATCH"):
        calculate_returns(data, factors, sessions=days)


@pytest.mark.parametrize(
    "session,event,accepted",
    [
        ("2024-01-31", "2024-02-01T00:30:00+00:00", True),  # same local day
        ("2024-02-01", "2024-02-01T00:30:00+00:00", False),  # same UTC date, wrong local day
        ("2024-01-31", "2024-02-01T05:00:00+00:00", False),  # next local midnight
        ("2024-06-30", "2024-07-01T03:59:59+00:00", True),
        ("2024-06-30", "2024-07-01T04:00:00+00:00", False),
        ("2023-12-31", "2024-01-01T01:00:00+00:00", True),
        ("2024-02-29", "2024-03-01T02:00:00+00:00", True),
    ],
)
def test_explicit_event_uses_local_date_and_half_open_bounds(session, event, accepted):
    row = quote(date.fromisoformat(session))
    event = datetime.fromisoformat(event)
    row = replace(row, event_time=event, observation_end=event)
    report = validate_quality(history((row,)))
    assert bool(report.accepted) == accepted
    assert ("SESSION_TIME_MISMATCH" in {i.code for i in report.issues}) != accepted


@pytest.mark.parametrize(
    "session,bound",
    [
        ("2024-01-31", "2024-02-01T05:00:00+00:00"),
        ("2024-05-31", "2024-06-01T04:00:00+00:00"),
        ("2024-03-10", "2024-03-11T04:00:00+00:00"),  # 23-hour local date
        ("2023-11-05", "2023-11-06T05:00:00+00:00"),  # 25-hour local date
    ],
)
def test_declared_upper_bound_preserves_unknown_event_and_dst(session, bound):
    row = replace(
        quote(date.fromisoformat(session)),
        event_time=None,
        observation_end=datetime.fromisoformat(bound),
    )
    data = history((row,), timestamp_basis="exchange_local_date_upper_bound")
    report = validate_quality(data)
    assert report.accepted == (row,) and report.quarantined == ()
    assert row.available_at == STAMP and row.event_time is None
    assert "SESSION_TIME_UNVERIFIED" in {i.code for i in report.issues}


@pytest.mark.parametrize("basis", ["explicit_source_timestamps", "exchange_local_date_upper_bound"])
def test_future_observation_end_cannot_be_hidden_by_unknown_event(basis):
    row = replace(
        quote(date(2022, 6, 30)),
        event_time=None,
        observation_end=datetime(2022, 7, 30, 4, tzinfo=UTC),
    )
    report = validate_quality(history((row,), timestamp_basis=basis))
    assert not report.accepted
    assert "SESSION_TIME_MISMATCH" in {i.code for i in report.issues}


def test_declared_upper_bound_cannot_use_wrong_dst_offset():
    row = replace(
        quote(date(2024, 5, 31)),
        event_time=None,
        observation_end=datetime(2024, 6, 1, 5, tzinfo=UTC),
    )
    report = validate_quality(history((row,), timestamp_basis="exchange_local_date_upper_bound"))
    assert not report.accepted
    assert "SESSION_TIME_MISMATCH" in {i.code for i in report.issues}


@pytest.mark.parametrize("availability_basis", ["declared", "retrieved_snapshot"])
def test_download_and_availability_do_not_relabel_historical_event(availability_basis):
    days = (date(2022, 6, 29), date(2022, 6, 30))
    rows = tuple(quote(d, D(v)) for d, v in zip(days, (100, 110), strict=True))
    if availability_basis == "declared":
        rows = tuple(replace(r, available_at=r.event_time + timedelta(minutes=1)) for r in rows)
    data = history(rows, availability_basis=availability_basis)
    assert validate_quality(data).accepted == rows
    returns = calculate_returns(data, factor_data("daily", days))
    assert returns.rows[0].value == D(".1")
    assert returns.rows[0].available_at == STAMP  # later downloaded vintage stays later


@pytest.mark.parametrize("missing_evidence", ["basis", "exchange", "tzdata", "event"])
def test_insufficient_time_evidence_is_explicitly_descriptive(monkeypatch, missing_evidence):
    days = (date(2022, 6, 29), date(2022, 6, 30))
    data = history(quote(d) for d in days)
    if missing_evidence == "basis":
        data = replace(data, timestamp_basis="unknown_vendor_semantics")
    elif missing_evidence == "exchange":
        data = replace(
            data,
            rows=tuple(replace(r, asset=replace(ASSET, exchange="UNKNOWN")) for r in data.rows),
        )
    elif missing_evidence == "tzdata":

        def unavailable(_):
            raise ZoneInfoNotFoundError("test: no IANA data")

        monkeypatch.setattr(data_contracts, "ZoneInfo", unavailable)
    else:
        data = replace(data, rows=tuple(replace(r, event_time=None) for r in data.rows))
    report = validate_quality(data)
    assert len(report.accepted) == 2
    notes = [i for i in report.issues if i.code == "SESSION_TIME_UNVERIFIED"]
    assert notes and all(
        i.severity == "WARNING" and "strict historical" in i.message for i in notes
    )
    returns = calculate_returns(data, factor_data("daily", days))
    assert any(
        "SESSION_TIME_UNVERIFIED" in w and "strict historical" in w for w in returns.warnings
    )


def test_distant_known_event_is_rejected_even_without_timezone_database(monkeypatch):
    def unavailable(_):
        raise ZoneInfoNotFoundError("test: no IANA data")

    monkeypatch.setattr(data_contracts, "ZoneInfo", unavailable)
    row = replace(quote(date(2022, 7, 29)), session_date=date(2022, 6, 30))
    assert "SESSION_TIME_MISMATCH" in {i.code for i in validate_quality(history((row,))).issues}


@pytest.mark.parametrize("exchange", ["XNAS", "XNYS", "XASE", "ARCX", "BATS"])
def test_supported_us_exchange_identities_use_eastern_local_dates(exchange):
    row = replace(quote(date(2024, 1, 31)), asset=replace(ASSET, exchange=exchange))
    event = datetime(2024, 2, 1, 1, tzinfo=UTC)
    row = replace(row, event_time=event, observation_end=event)
    assert validate_quality(history((row,))).accepted == (row,)


def test_daily_quarantine_keeps_gaps_and_trailing_regression_boundaries():
    days = []
    day = date(2023, 1, 2)
    while len(days) < 40:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    rows, factors = [], []
    price = D(100)
    for i, day in enumerate(days):
        x = tuple(
            D(str(0.01 * math.sin(a * i + b)))
            for a, b in ((0.71, 0.1), (0.57, 0.7), (0.39, 0.9), (0.91, 0.3))
        )
        factors.append(FactorRow(day, *x[:3], D(".001"), x[3]))
        if i:
            price *= 1 + D(".001") + sum(x) + D(str(0.0001 * math.cos(i)))
        rows.append(quote(day, price))
    bad = list(rows)
    bad[13] = replace(bad[14], session_date=days[13])
    report = validate_quality(history(bad))
    assert len(report.quarantined) == 1
    data = history(report.accepted)
    factors = FactorData("daily", tuple(factors), "synthetic R5 daily", STAMP, {}, True)
    returns = calculate_returns(data, factors)
    sample = align_common_sample(returns, factors, days[1], days[-1] + timedelta(days=1))
    assert {e["period"] for e in sample.exclusions} == {str(days[13]), str(days[14])}
    assert len(sample.rows) == 37
    windows = rolling_exposures(sample, 12, min_obs=6)
    assert len(windows) == 28
    for i, window in enumerate(windows):
        assert window["window_start"] == str(days[i + 1])
        assert window["window_end"] == str(days[i + 12])
        selected = [r for r in sample.rows if days[i + 1] <= r.period <= days[i + 12]]
        assert window["nobs"] == len(selected)
        x = np.array([[1, *r.factors] for r in selected])
        y = np.array([r.excess_return for r in selected])
        q, r = np.linalg.qr(x, mode="reduced")
        expected = np.linalg.solve(r, q.T @ y)
        actual = window["comparison"]["fits"]["FF4"]["coefficients"]
        np.testing.assert_allclose([v["estimate"] for v in actual.values()], expected, atol=1e-11)
    perturbed = replace(
        sample,
        rows=tuple(
            replace(r, excess_return=r.excess_return + 0.1) if r.period > days[24] else r
            for r in sample.rows
        ),
    )
    assert windows[:13] == rolling_exposures(perturbed, 12, min_obs=6)[:13]


def monthly_inputs():
    dates = []
    for y, months in ((2021, (12,)), (2022, range(1, 13)), (2023, range(1, 13))):
        for m in months:
            day = date(y, m, calendar.monthrange(y, m)[1])
            while day.weekday() >= 5:
                day -= timedelta(days=1)
            dates.append(day)
    rows, factors = [], []
    price = D(100)
    for i, day in enumerate(dates):
        if i:
            x = tuple(
                D(str(0.02 * math.sin(a * i + b)))
                for a, b in ((0.71, 0.1), (0.57, 0.7), (0.39, 0.9), (0.91, 0.3))
            )
            price *= (
                1
                + D(".001")
                + sum(a * b for a, b in zip(x, map(D, (".9", "-.3", ".4", ".6")), strict=True))
            )
            price *= 1 + D(str(0.0001 * math.cos(i)))
            period = date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])
            factors.append(FactorRow(period, *x[:3], D(".001"), x[3]))
        rows.append(quote(day, price))
    return (
        history(rows),
        FactorData("monthly", tuple(factors), "synthetic R5", STAMP, {}, True),
        tuple(dates),
    )


def test_clean_quarantine_replay_preserves_month_grid_and_rolling_math():
    good, factors, sessions = monthly_inputs()
    target = next(i for i, r in enumerate(good.rows) if r.session_date == date(2022, 6, 30))
    rows = list(good.rows)
    rows[target] = replace(rows[target + 1], session_date=rows[target].session_date)
    report = validate_quality(replace(good, rows=tuple(rows)))
    assert len(report.quarantined) == 1
    clean = replace(good, rows=report.accepted)  # explicit analyst quarantine, no relabel/repair
    returns = calculate_returns(clean, factors, sessions=sessions)
    sample = align_common_sample(returns, factors, date(2022, 1, 1), date(2024, 1, 1))
    assert len(sample.rows) == 22
    assert {e["period"] for e in sample.exclusions} == {"2022-06-30", "2022-07-31"}
    windows = rolling_exposures(sample, 12, min_obs=6)
    assert len(windows) == 13 and windows[0]["nobs"] == 10
    for window in windows:
        selected = [
            r
            for r in sample.rows
            if window["window_start"] <= str(r.period) <= window["window_end"]
        ]
        x = np.array([[1, *r.factors] for r in selected])
        y = np.array([r.excess_return for r in selected])
        q, r = np.linalg.qr(x, mode="reduced")
        expected = np.linalg.solve(r, q.T @ y)
        actual = window["comparison"]["fits"]["FF4"]["coefficients"]
        np.testing.assert_allclose([v["estimate"] for v in actual.values()], expected, atol=1e-11)
        assert window["historical_signal_eligible"] is False
    perturbed = replace(
        sample,
        rows=tuple(
            replace(r, excess_return=r.excess_return + 0.1) if r.period.year == 2023 else r
            for r in sample.rows
        ),
    )
    assert windows[0] == rolling_exposures(perturbed, 12, min_obs=6)[0]


@pytest.mark.parametrize("frequency", ["daily", "monthly"])
def test_r5_native_csv_public_cli_exits_2_before_any_regression(
    tmp_path: Path, capsys, monkeypatch, frequency
):
    data, factors, sessions = monthly_inputs()
    target = next(i for i, r in enumerate(data.rows) if r.session_date == date(2022, 6, 30))
    rows = list(data.rows)
    rows[target] = replace(rows[target + 1], session_date=rows[target].session_date)
    write_history(replace(data, rows=tuple(rows)), tmp_path / "prices.csv")
    stamp = "%Y%m" if frequency == "monthly" else "%Y%m%d"
    (tmp_path / "ff3.csv").write_text(
        ",Mkt-RF,SMB,HML,RF\n"
        + "\n".join(
            r.period.strftime(stamp)
            + ","
            + ",".join(str(v * 100) for v in (r.mkt_rf, r.smb, r.hml, r.rf))
            for r in factors.rows
        ),
        encoding="utf-8",
    )
    (tmp_path / "mom.csv").write_text(
        ",Mom\n"
        + "\n".join(r.period.strftime(stamp) + "," + str(r.mom * 100) for r in factors.rows),
        encoding="utf-8",
    )
    (tmp_path / "sessions.txt").write_text("\n".join(map(str, sessions)), encoding="utf-8")
    config = tmp_path / "factors.toml"
    config.write_text(
        'schema_version=3\nexpected_kind="synthetic"\nfactor_source="local"\n'
        'price_file="prices.csv"\nff3_file="ff3.csv"\nmomentum_file="mom.csv"\n'
        'start="2022-01-01"\nend="2024-01-01"\nmin_obs=6\nrolling_window=12\n'
        f'frequency="{frequency}"\n'
        + ('sessions_file="sessions.txt"\n' if frequency == "monthly" else ""),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        factor_cli, "run_factor_research", lambda c: run_factor_research(c, clock=lambda: STAMP)
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
                "r5-rejected",
            ]
        )
    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == "" and "SESSION_TIME_MISMATCH" in output.err
    assert not (tmp_path / "reports" / "r5-rejected").exists()
