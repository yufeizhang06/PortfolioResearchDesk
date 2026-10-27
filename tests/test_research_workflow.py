import json
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from portfolio_research_desk.data_adapters import LocalHistoryAdapter, ProviderError
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.research_config import load_research_config
from portfolio_research_desk.research_workflow import run_research, save_research_run

STAMP = datetime(2024, 1, 10, 23, tzinfo=UTC)


def config(tmp_path):
    return replace(
        load_research_config(), cache_dir=tmp_path / "cache", output_dir=tmp_path / "runs"
    )


@pytest.mark.parametrize("mode", ["custom", "market", "screening"])
def test_all_universe_modes_and_combinations_work_offline(tmp_path, mode):
    cfg = config(tmp_path)
    if mode == "market":
        cfg = replace(cfg, universe_mode=mode, directory_fixture=True, assets=())
    else:
        cfg = replace(cfg, universe_mode=mode)
    first = run_research(cfg, clock=lambda: STAMP)
    assert first.status == "complete" and len(first.universe.assets) == 3
    assert first.universe.screening_applied and len(first.screening.decisions) == 3
    second = run_research(cfg, clock=lambda: STAMP + timedelta(minutes=1))
    assert all(event["hit"] for event in second.cache_events)
    assert [h.snapshot_hash for h in first.histories] == [h.snapshot_hash for h in second.histories]
    directory = save_research_run(second, cfg)
    payload = json.loads((directory / "run.json").read_text())
    assert payload["historical_pit_verified"] is False
    assert len(payload["history_files"]) == len(second.histories)
    for item, history in zip(payload["history_files"], second.histories, strict=True):
        assert (directory / item["metadata"]).is_file()
        assert LocalHistoryAdapter(directory / item["csv"]).read() == history


def test_export_failure_cannot_write_a_completed_run(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    result = run_research(cfg, clock=lambda: STAMP)

    def failed_export(*_args):
        raise DataError("Disk export failed.")

    monkeypatch.setattr("portfolio_research_desk.research_workflow.write_history", failed_export)
    with pytest.raises(DataError, match="export failed"):
        save_research_run(result, cfg)
    assert not list(cfg.output_dir.rglob("run.json"))


def test_plain_market_universe_does_not_download_thousands_of_histories(tmp_path):
    cfg = replace(
        config(tmp_path), universe_mode="market", directory_fixture=True, assets=(), rules=None
    )
    result = run_research(cfg, clock=lambda: STAMP)
    assert len(result.universe.assets) == 3 and not result.histories
    assert len(result.cache_events) == 1


def test_request_budget_has_no_silent_truncation(tmp_path):
    with pytest.raises(DataError, match="budget"):
        run_research(replace(config(tmp_path), max_assets=2), clock=lambda: STAMP)


def real_config(tmp_path):
    cfg = config(tmp_path)
    assets = tuple(
        replace(a, symbol=s) for a, s in zip(cfg.assets, ("AAPL", "MSFT", "NVDA"), strict=True)
    )
    return replace(
        cfg, assets=assets, adapter="yfinance", local_file=None, expected_kind="real", offline=False
    )


class TestTransport:
    __test__ = False

    def __init__(self, cfg, failure=None):
        fixture = LocalHistoryAdapter(load_research_config().local_file).read()
        self.histories = {}
        for old, asset in zip(
            dict.fromkeys(r.asset for r in fixture.rows), cfg.assets, strict=True
        ):
            rows = tuple(replace(row, asset=asset) for row in fixture.rows if row.asset == old)
            self.histories[asset] = replace(
                fixture, rows=rows, data_kind="real", price_basis="raw_declared"
            )
        self.calls = []
        self.failure = failure

    def cache_identity(self):
        return {"adapter": "test_injected_provider", "version": 1}

    def fetch(self, asset, start, end):
        self.calls.append(asset)
        if self.failure and asset.symbol == "AAPL":
            raise self.failure
        return self.histories[asset]


def test_cache_reuse_never_calls_provider_again(tmp_path):
    cfg = real_config(tmp_path)
    transport = TestTransport(cfg)
    assert run_research(cfg, adapter=transport, clock=lambda: STAMP).status == "complete"
    assert len(transport.calls) == 3
    transport.fetch = lambda *_args: pytest.fail("cached replay called the remote provider")
    second = run_research(replace(cfg, offline=True), adapter=transport, clock=lambda: STAMP)
    assert all(e["hit"] for e in second.cache_events)


def test_offline_cache_miss_never_calls_provider(tmp_path):
    cfg = replace(real_config(tmp_path), offline=True)
    transport = TestTransport(cfg)
    result = run_research(cfg, adapter=transport, clock=lambda: STAMP)
    assert result.status == "failed" and len(result.failures) == 3
    assert not transport.calls


def test_partial_failure_is_reported_and_other_assets_continue(tmp_path):
    cfg = real_config(tmp_path)
    transport = TestTransport(cfg, ProviderError("NO_DATA", "missing"))
    result = run_research(cfg, adapter=transport, clock=lambda: STAMP)
    assert result.status == "partial" and len(result.histories) == 2
    assert result.failures[0]["asset"]["symbol"] == "AAPL"
    assert "DATA_UNAVAILABLE" in result.screening.decisions[0].reasons


def test_rate_limit_stops_uncached_batch_requests(tmp_path):
    cfg = real_config(tmp_path)
    transport = TestTransport(cfg, ProviderError("RATE_LIMIT", "quota", True))
    result = run_research(cfg, adapter=transport, clock=lambda: STAMP)
    assert result.status == "failed" and len(result.failures) == 3
    assert len(transport.calls) == 1


def test_adapter_cannot_replace_real_market_failure_with_synthetic_data(tmp_path):
    cfg = real_config(tmp_path)
    transport = TestTransport(cfg)
    synthetic = LocalHistoryAdapter(load_research_config().local_file).read()
    transport.fetch = lambda *_args: synthetic
    result = run_research(cfg, adapter=transport, clock=lambda: STAMP)
    assert result.status == "failed" and not result.histories


def test_market_directory_offline_miss_and_pit_requirement_are_blocked(tmp_path):
    cfg = replace(real_config(tmp_path), universe_mode="market", assets=(), offline=True)
    with pytest.raises(DataError, match="Offline directory"):
        run_research(cfg, clock=lambda: STAMP)
    cfg = replace(
        config(tmp_path),
        universe_mode="market",
        directory_fixture=True,
        assets=(),
        require_point_in_time=True,
    )
    with pytest.raises(DataError, match="PIT"):
        run_research(cfg, clock=lambda: STAMP)


def test_screening_rejects_unavailable_universe_and_calendar_gaps(tmp_path):
    cfg = replace(config(tmp_path), as_of=STAMP - timedelta(days=5))
    result = run_research(cfg, clock=lambda: STAMP)
    assert all("UNIVERSE_UNAVAILABLE" in d.reasons for d in result.screening.decisions)
    cfg = replace(
        config(tmp_path), expected_sessions=(*config(tmp_path).expected_sessions, STAMP.date())
    )
    result = run_research(cfg, clock=lambda: STAMP)
    assert result.status == "partial"
    assert not result.universe.assets
    assert all("QUALITY_MISSING_SESSION" in d.reasons for d in result.screening.decisions)


def test_installed_cli_offline_pipeline_and_watchlist_commands(tmp_path):
    process = subprocess.run(
        [sys.executable, "-I", "-m", "portfolio_research_desk", "universe", "build"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(process.stdout)
    assert (
        payload["phase"] == 2
        and payload["data_kind"] == "synthetic"
        and payload["status"] == "complete"
    )
    csv_file = tmp_path / "custom.csv"
    csv_file.write_text(
        "market,exchange,symbol,currency\nUS,XNAS,AAPL,USD\nUS,XNAS,AAPL,USD\n", encoding="utf-8"
    )
    saved = tmp_path / "watch.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "portfolio_research_desk",
            "universe",
            "watchlist",
            "import",
            "--input",
            str(csv_file),
            "--output",
            str(saved),
            "--kind",
            "real",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert len(json.loads(result.stdout)["universe"]["assets"]) == 1
