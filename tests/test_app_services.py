"""Offline application integration: real saved snapshots and existing engines."""

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from portfolio_research_desk.app_contracts import FactorRequest, HistoryRequest
from portfolio_research_desk.app_services import DeskService, preview_watchlist
from portfolio_research_desk.delivery_reports import file_hash, verify_workflow_report
from portfolio_research_desk.domain import AssetId
from portfolio_research_desk.errors import ConfigError, DataError
from portfolio_research_desk.factor_workflow import run_factor_research

ASSET = AssetId("US", "XNAS", "SYN_FACTOR", "USD")
AT = datetime(2026, 10, 29, tzinfo=UTC)
HISTORY = HistoryRequest((ASSET,), date(2024, 1, 1), date(2024, 6, 1))


@pytest.fixture
def service(tmp_path):
    desk = DeskService(tmp_path / "desk", clock=lambda: AT)
    desk.create()
    return desk


@pytest.fixture
def history(service):
    ref = service.fetch(HISTORY, "a" * 32)
    return service.histories(ref)[0][1]


def test_preserves_watchlist_identity_versions_and_deduplicates(service):
    text = "market,exchange,symbol,currency\nUS,XNAS,SYN_FACTOR,USD\nUS,XNAS,SYN_FACTOR,USD\n"
    assets, duplicates, errors = preview_watchlist(text, True)
    assert assets == (ASSET,) and duplicates == [3] and not errors
    path = service.save_list("study", assets, True)
    assert service.save_list("study", assets, True) == path
    reopened = DeskService(service.root).load_list(path)
    assert reopened.assets == assets and reopened.synthetic and reopened.as_of == AT


@pytest.mark.parametrize(
    "text",
    [
        "symbol\nAAPL",
        "market,exchange,symbol,currency\nUS,XNAS,AAPL,USD",
        "market,exchange,symbol,currency\nUS,UNKNOWN,SYN_FACTOR,USD",
        "market,exchange,symbol,currency\nUS,XNAS,SYN_FACTOR",
    ],
)
def test_invalid_watchlists_are_not_silently_accepted(text):
    try:
        _, _, errors = preview_watchlist(text, True)
        assert errors
    except DataError:
        pass


@pytest.mark.parametrize("path", ["../outside", "/outside", "C:/outside", "gui/../../outside"])
def test_workspace_path_escape_is_rejected(service, path):
    if path == "C:/outside" and Path(path).drive == "":
        pytest.skip("Windows drive path")
    with pytest.raises(DataError):
        service.path(path)


def test_snapshot_reopens_exactly_and_duplicate_submit_reuses_task(service, history):
    ref = service.fetch(HISTORY, "a" * 32)
    assert ref.status == "complete"
    reopened = DeskService(service.root)
    assert reopened.history(history).snapshot_hash == service.history(history).snapshot_hash
    with pytest.raises(DataError, match="输入已变化"):
        service.fetch(replace(HISTORY, end=date(2024, 5, 1)), "a" * 32)
    assert len(service.tasks()) == 1


def test_factor_same_backend_same_snapshot_and_audit(service, history):
    request = FactorRequest(history, date(2024, 1, 2), date(2024, 6, 1))
    direct = run_factor_research(service.factor_config(request))
    ref = service.study(request, "b" * 32)
    data = service.factor_data(ref)
    assert data["analysis"] == direct.comparison
    assert data["run"]["nobs"] == len(direct.sample.rows) == 96
    assert data["run"]["historical_signal_eligible"] is False
    assert data["price_snapshot"]["data_kind"] == "synthetic"
    assert service.study(request, "b" * 32) == ref
    html = service.path(ref.directory) / "report.html"
    assert "0.0200%" in html.read_text("utf-8")
    html.write_text("changed", encoding="utf-8")
    with pytest.raises(DataError, match="完整性"):
        service.factor_data(ref)
    assert any(error for _, error in service.tasks())


def test_service_cannot_replace_real_assets_with_synthetic(service):
    real = AssetId("US", "XNAS", "AAPL", "USD")
    with pytest.raises(DataError):
        service.fetch(replace(HISTORY, assets=(real,), expected_kind="real"), "c" * 32)
    with pytest.raises(DataError):
        service.fetch(replace(HISTORY, source="yfinance"), "c" * 32)
    assert not service.tasks()


def test_offline_real_cache_miss_no_synthetic_fallback(service):
    real = AssetId("US", "XNAS", "AAPL", "USD")
    ref = service.fetch(
        replace(HISTORY, assets=(real,), expected_kind="real", source="yfinance"), "c" * 32
    )
    assert ref.status == "failed"
    assert service.histories(ref) == []
    assert (
        "no network request"
        in service._json(service.path(ref.directory) / "run.json")["result"]["failures"][0][
            "reason"
        ]
    )


def test_factor_constraints_reject_mixed_modes_and_monthly_fixture(service, history):
    request = FactorRequest(history, date(2024, 1, 2), date(2024, 6, 1))
    with pytest.raises(ConfigError):
        service.check_factor(replace(request, frequency="monthly"))
    with pytest.raises(ConfigError):
        service.check_factor(replace(request, rolling_window=6))
    with pytest.raises(DataError):
        service.history("factors.toml")


def test_insufficient_sample_saved_as_failed_not_success(service, history):
    request = FactorRequest(history, date(2024, 1, 2), date(2024, 1, 5))
    ref = service.study(request, "d" * 32)
    assert ref.status == "failed"
    assert service.factor_data(ref)["analysis"] is None


def test_incomplete_task_not_reexecuted_or_falsely_completed(service):
    with pytest.raises(RuntimeError):
        service._execute(
            "e" * 32, "test", {}, lambda _: (_ for _ in ()).throw(RuntimeError("stop"))
        )
    with pytest.raises(DataError):
        service._execute("e" * 32, "test", {}, lambda _: pytest.fail("must not execute"))
    assert service.tasks()[0][1]


def test_capabilities_block_trading_and_real_backtest(service):
    for capability in ("real_backtest", "paper_writes", "broker"):
        with pytest.raises(DataError):
            service.require(capability)


def test_demo_new_account_and_read_only_nav(service):
    ref = service.demo("f" * 32)
    verify_workflow_report(service.path(ref.directory))
    account = service.path(ref.directory) / "account.sqlite3"
    before = file_hash(account)
    summary = service.read_account(service.relative(account))
    assert str(summary["last_recorded_valuation"].nav_cad) == "2971.1700"
    assert not summary["valuation_stale"]
    assert file_hash(account) == before
    assert service.demo("f" * 32) == ref
