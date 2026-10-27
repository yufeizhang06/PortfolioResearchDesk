from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from importlib.resources import files

import pytest

from portfolio_research_desk.errors import DataError
from portfolio_research_desk.market_data import (
    load_backtest_dataset,
    parse_synthetic_dataset,
    validate_dataset,
)


def test_explicit_six_session_complete_panel():
    dataset = load_backtest_dataset()
    assert len(dataset.bars) == 18
    assert len(dataset.sessions) == 6
    assert dataset == load_backtest_dataset()
    assert len(dataset.data_hash) == 64
    assert dataset.sessions[3].session_date.weekday() == 4
    assert dataset.sessions[4].session_date.weekday() == 0


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "adjusted", "currency", "actions", "calendar", "source"]
)
def test_unusable_panels_fail_closed(change):
    dataset = load_backtest_dataset()
    first, *rest = dataset.bars
    if change == "missing":
        dataset = replace(dataset, bars=tuple(rest))
    elif change == "duplicate":
        dataset = replace(dataset, bars=dataset.bars + (first,))
    elif change == "adjusted":
        dataset = replace(dataset, bars=(replace(first, adjusted=True), *rest))
    elif change == "currency":
        dataset = replace(
            dataset, bars=(replace(first, asset=replace(first.asset, currency="CAD")), *rest)
        )
    elif change == "actions":
        dataset = replace(dataset, corporate_actions="split")
    elif change == "calendar":
        dataset = replace(dataset, sessions=dataset.sessions[::-1])
    else:
        dataset = replace(dataset, source="real_vendor")
    with pytest.raises(DataError):
        validate_dataset(dataset)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("close", D("0")),
        ("close", D("NaN")),
        ("high", D("1")),
        ("low", D("50")),
        ("open", D("10.001")),
        ("volume", -1),
        ("volume", True),
    ],
)
def test_price_contract_rejects_invalid_numbers(field, value):
    with pytest.raises(DataError):
        replace(load_backtest_dataset().bars[0], **{field: value})


def test_naive_and_impossible_availability_are_rejected():
    bar = load_backtest_dataset().bars[0]
    with pytest.raises(DataError):
        replace(bar, available_at=bar.available_at.replace(tzinfo=None))
    with pytest.raises(DataError):
        replace(bar, available_at=bar.event_time - timedelta(seconds=1))


@pytest.mark.parametrize("kind", ["columns", "short", "boolean", "number", "manifest", "encoding"])
def test_malformed_csv_or_manifest_is_reported(kind):
    root = files("portfolio_research_desk").joinpath("resources")
    raw = root.joinpath("backtest_prices.csv").read_bytes()
    manifest = root.joinpath("backtest_sessions.toml").read_bytes()
    if kind == "columns":
        raw = raw.replace(b"market,exchange", b"bad,exchange", 1)
    elif kind == "short":
        raw = raw.splitlines()[0] + b"\nUS,SYNTHETIC\n"
    elif kind == "boolean":
        raw = raw.replace(b",true", b",maybe", 1)
    elif kind == "number":
        raw = raw.replace(b",10.00,", b",invalid,", 1)
    elif kind == "manifest":
        manifest = b"[broken"
    else:
        raw = b"\xff"
    with pytest.raises(DataError):
        parse_synthetic_dataset(raw, manifest)
