from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from importlib.resources import files
from pathlib import Path

import pytest

from portfolio_research_desk.data_adapters import LocalHistoryAdapter
from portfolio_research_desk.domain import AssetId
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.screening import ScreenRules, screen_universe
from portfolio_research_desk.universe import (
    custom_universe,
    ensure_historical_use,
    export_watchlist,
    import_watchlist,
    load_watchlist,
    parse_nasdaq_directory,
    save_watchlist,
    update_watchlist,
)


def fixture():
    root = files("portfolio_research_desk").joinpath("resources")
    data = LocalHistoryAdapter(Path(str(root.joinpath("research_prices.csv")))).read()
    assets = tuple(dict.fromkeys(r.asset for r in data.rows))
    stamp = datetime(2024, 1, 10, tzinfo=UTC)
    snapshot = custom_universe(assets, datetime(2024, 1, 1, tzinfo=UTC), True)
    histories = {
        asset: replace(data, rows=tuple(r for r in data.rows if r.asset == asset))
        for asset in assets
    }
    rules = ScreenRules(3, 1, D("0"), 2, D("10"), 2, D("1000"))
    return snapshot, histories, rules, stamp


def test_watchlist_dedup_save_read_import_export_update(tmp_path):
    snapshot, _, _, stamp = fixture()
    snapshot = custom_universe((*snapshot.assets, snapshot.assets[0]), snapshot.as_of, True)
    assert len(snapshot.assets) == 3
    path = tmp_path / "list.json"
    save_watchlist(snapshot, path)
    assert load_watchlist(path) == snapshot
    with pytest.raises(DataError, match="exists"):
        save_watchlist(snapshot, path)
    csv_path = tmp_path / "list.csv"
    export_watchlist(snapshot, csv_path)
    imported = import_watchlist(csv_path, snapshot.as_of, True)
    assert imported.assets == snapshot.assets
    new = AssetId("US", "XNAS", "SYN_D", "USD")
    changed = update_watchlist(snapshot, (new, new), ("SYN_A",), stamp)
    assert {a.symbol for a in changed.assets} == {"SYN_B", "SYN_C", "SYN_D"}
    save_watchlist(changed, path, True)
    assert load_watchlist(path) == changed


def test_current_market_snapshot_is_never_historical_pit():
    raw = files("portfolio_research_desk").joinpath("resources/research_directory.txt").read_bytes()
    stamp = datetime(2024, 1, 10, tzinfo=UTC)
    market = parse_nasdaq_directory(raw, stamp, True)
    assert market.universe.membership_type == "current_snapshot"
    assert len(market.universe.assets) == 3
    assert market.excluded[0]["reason"] == "ETF_TEST_OR_NEXTSHARES"
    with pytest.raises(DataError, match="PIT"):
        ensure_historical_use(market.universe, stamp + timedelta(days=1))
    with pytest.raises(DataError, match="mixed"):
        parse_nasdaq_directory(raw, stamp, False)
    with pytest.raises(DataError, match="marker"):
        parse_nasdaq_directory(raw.split(b"File Creation Time:")[0], stamp, True)


def test_three_rules_emit_values_reasons_and_availability():
    snapshot, histories, rules, stamp = fixture()
    screened = screen_universe(snapshot, histories, rules, stamp)
    assert len(screened.universe.assets) == 3
    assert all(
        d.available_at <= stamp and d.value_as_of.isoformat() == "2024-01-09"
        for d in screened.decisions
    )
    rejected = screen_universe(
        snapshot, histories, replace(rules, min_dollar_volume=D("1e20")), stamp
    )
    assert rejected.universe.assets == () and rejected.universe.screening_applied
    assert all(d.reasons == ("LIQUIDITY_BELOW_MIN",) for d in rejected.decisions)
    rejected = screen_universe(
        snapshot, histories, replace(rules, max_volatility=D("0"), min_momentum=D("10")), stamp
    )
    assert all("MOMENTUM_BELOW_MIN" in d.reasons for d in rejected.decisions)


def test_future_perturbation_does_not_change_past_screening():
    snapshot, histories, rules, _ = fixture()
    stamp = datetime(2024, 1, 5, 22, tzinfo=UTC)
    before = screen_universe(snapshot, histories, rules, stamp)
    changed = {
        asset: replace(
            h,
            rows=tuple(
                replace(row, close=row.close * 4, high=row.high * 4)
                if row.observation_end > stamp
                else row
                for row in h.rows
            ),
        )
        for asset, h in histories.items()
    }
    assert screen_universe(snapshot, changed, rules, stamp) == before


def test_late_input_missing_history_and_mixed_kind_are_explicit():
    snapshot, histories, rules, stamp = fixture()
    first = snapshot.assets[0]
    late = dict(histories)
    late[first] = replace(
        histories[first],
        rows=tuple(
            replace(r, available_at=stamp + timedelta(days=1)) for r in histories[first].rows
        ),
    )
    result = screen_universe(snapshot, late, rules, stamp)
    assert "INPUT_UNAVAILABLE" in result.decisions[0].reasons
    assert "DATA_UNAVAILABLE" in screen_universe(snapshot, {}, rules, stamp).decisions[0].reasons
    real_asset = replace(first, symbol="AAPL")
    real_history = replace(
        histories[first],
        data_kind="real",
        price_basis="raw_declared",
        rows=tuple(replace(r, asset=real_asset) for r in histories[first].rows),
    )
    with pytest.raises(DataError):
        screen_universe(snapshot, {first: real_history}, rules, stamp)
