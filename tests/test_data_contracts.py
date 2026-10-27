from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from portfolio_research_desk.data_contracts import History, Observation, validate_quality
from portfolio_research_desk.domain import AssetId
from portfolio_research_desk.errors import DataError


def history():
    stamp = datetime(2024, 1, 3, 22, tzinfo=UTC)
    row = Observation(
        AssetId("US", "XNAS", "SYN_A", "USD"),
        stamp.date(),
        stamp,
        stamp,
        stamp,
        D("10"),
        D("11"),
        D("9"),
        D("10"),
        1000,
    )
    return History(
        "synthetic",
        "self_authored",
        "synthetic_raw",
        "declared",
        stamp,
        (row,),
        ("Self-authored fixture, not market evidence.",),
    )


def test_duplicate_and_missing_prices_are_quarantined_not_filled():
    data = history()
    report = validate_quality(replace(data, rows=(data.rows[0], data.rows[0])))
    assert not report.accepted
    assert any(issue.code == "DUPLICATE" for issue in report.issues)
    report = validate_quality(replace(data, rows=(replace(data.rows[0], close=None),)))
    assert not report.accepted
    assert any(issue.code == "MISSING_PRICE" for issue in report.issues)


def test_real_and_synthetic_identity_cannot_be_mixed():
    with pytest.raises(DataError):
        replace(history(), data_kind="real")


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("close", D("0"), "INVALID_PRICE"),
        ("close", D("NaN"), "INVALID_PRICE"),
        ("high", D("1"), "OHLC_BOUNDS"),
        ("volume", None, "INVALID_VOLUME"),
        ("volume", -1, "INVALID_VOLUME"),
        ("volume", True, "INVALID_VOLUME"),
        ("dividend", None, "CORPORATE_ACTION"),
        ("adj_close", D("NaN"), "ADJUSTED_PRICE"),
    ],
)
def test_bad_provider_values_are_quarantined(field, value, code):
    data = history()
    report = validate_quality(replace(data, rows=(replace(data.rows[0], **{field: value}),)))
    assert not report.accepted and report.quarantined
    assert code in {issue.code for issue in report.issues}


def test_declared_missing_session_and_incomplete_bar_are_not_fabricated():
    from datetime import timedelta

    data = history()
    report = validate_quality(
        data, (data.rows[0].session_date, data.rows[0].session_date + timedelta(days=1))
    )
    assert any(i.code == "MISSING_SESSION" for i in report.issues)
    invalid = replace(
        data.rows[0], available_at=data.rows[0].observation_end - timedelta(seconds=1)
    )
    assert not validate_quality(replace(data, rows=(invalid,))).accepted
