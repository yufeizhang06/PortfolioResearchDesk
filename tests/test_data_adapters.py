from datetime import UTC, date, datetime
from importlib.resources import files
from pathlib import Path

import pytest

from portfolio_research_desk.data_adapters import (
    LocalHistoryAdapter,
    ProviderError,
    RetryPolicy,
    YFinanceAdapter,
    _retry_after_seconds,
    retry_call,
    write_history,
)
from portfolio_research_desk.data_contracts import validate_quality
from portfolio_research_desk.domain import AssetId
from portfolio_research_desk.errors import DataError


def fixture_history():
    return LocalHistoryAdapter(
        Path(str(files("portfolio_research_desk").joinpath("resources/research_prices.csv")))
    ).read()


@pytest.mark.parametrize("extension", ["csv", "parquet"])
def test_local_adapters_preserve_exact_contract_and_precision(tmp_path, extension):
    if extension == "parquet":
        pytest.importorskip("pyarrow")
    history = fixture_history()
    path = tmp_path / f"prices.{extension}"
    write_history(history, path)
    adapter = LocalHistoryAdapter(path)
    assert adapter.read() == history
    first = history.rows[0]
    subset = adapter.fetch(first.asset, first.session_date, date(2024, 1, 4))
    assert len(subset.rows) == 2
    assert {row.asset for row in subset.rows} == {first.asset}
    assert adapter.cache_identity()["content_hash"]
    with pytest.raises(DataError, match="overwrite"):
        write_history(history, path)


def test_csv_requires_metadata_and_detects_tampering(tmp_path):
    path = tmp_path / "prices.csv"
    write_history(fixture_history(), path)
    path.write_bytes(path.read_bytes().replace(b"10.00", b"99.00", 1))
    with pytest.raises(DataError, match="checksum"):
        LocalHistoryAdapter(path).read()
    path.with_suffix(".metadata.json").unlink()
    with pytest.raises(DataError):
        LocalHistoryAdapter(path).read()


def test_native_data_cannot_be_requested_under_a_different_identity(tmp_path):
    adapter = LocalHistoryAdapter(
        Path(str(files("portfolio_research_desk").joinpath("resources/research_prices.csv")))
    )
    with pytest.raises(ProviderError):
        adapter.fetch(AssetId("US", "XNYS", "SYN_A", "USD"), date(2024, 1, 2), date(2024, 1, 10))


def test_retry_is_bounded_and_does_not_bypass_a_long_retry_after():
    calls, sleeps = [], []

    def transient():
        calls.append(1)
        if len(calls) < 3:
            raise ProviderError("HTTP_503", "temporary", True)
        return "ok"

    assert retry_call(transient, RetryPolicy(base_delay=1), sleeps.append) == "ok"
    assert sleeps == [1, 2]
    calls.clear()

    def limited():
        calls.append(1)
        raise ProviderError("HTTP_429", "quota", True, retry_after=60)

    with pytest.raises(ProviderError):
        retry_call(limited, RetryPolicy(), sleeps.append)
    assert len(calls) == 1


def test_permanent_provider_failure_is_not_retried():
    calls = []

    def missing():
        calls.append(1)
        raise ProviderError("EMPTY", "missing")

    with pytest.raises(ProviderError):
        retry_call(missing, RetryPolicy(), lambda _: pytest.fail("should not sleep"))
    assert len(calls) == 1


def test_yfinance_adapter_records_retrieval_not_invented_publication(tmp_path):
    pd = pytest.importorskip("pandas")
    stamp = datetime(2024, 2, 1, tzinfo=UTC)
    recorded = {}
    frame = pd.DataFrame(
        {
            "Open": [10.0],
            "High": [11.0],
            "Low": [9.0],
            "Close": [10.5],
            "Volume": [1000],
            "Adj Close": [10.4],
            "Dividends": [0.0],
            "Stock Splits": [0.0],
        },
        index=pd.DatetimeIndex(["2024-01-02"], tz="America/New_York"),
    )

    class Ticker:
        def history(self, **kwargs):
            recorded.update(kwargs)
            return frame

        def get_history_metadata(self):
            return {
                "currency": "USD",
                "exchangeName": "NMS",
                "exchangeTimezoneName": "America/New_York",
            }

    adapter = YFinanceAdapter(tmp_path, factory=lambda _: Ticker(), clock=lambda: stamp)
    data = adapter.fetch(AssetId("US", "XNAS", "AAPL", "USD"), date(2024, 1, 1), date(2024, 1, 3))
    assert data.data_kind == "real" and data.availability_basis == "retrieved_snapshot"
    assert data.rows[0].available_at == stamp and data.rows[0].event_time is None
    assert data.rows[0].observation_end == datetime(2024, 1, 3, 5, tzinfo=UTC)
    assert (
        recorded["auto_adjust"] is False
        and recorded["repair"] is False
        and recorded["keepna"] is True
    )
    assert any(issue.code == "NOT_HISTORICAL_PIT" for issue in validate_quality(data).issues)
    frame.iloc[0, frame.columns.get_loc("Close")] = float("nan")
    changed = adapter.fetch(
        AssetId("US", "XNAS", "AAPL", "USD"), date(2024, 1, 1), date(2024, 1, 3)
    )
    assert not validate_quality(changed).accepted


def test_provider_identity_mismatch_fails_closed(tmp_path):
    pd = pytest.importorskip("pandas")

    class Wrong:
        def history(self, **_kwargs):
            return pd.DataFrame({"Close": [10]})

        def get_history_metadata(self):
            return {"currency": "CAD", "exchangeName": "NMS"}

    adapter = YFinanceAdapter(tmp_path, factory=lambda _: Wrong())
    with pytest.raises(ProviderError, match="IDENTITY"):
        adapter.fetch(AssetId("US", "XNAS", "AAPL", "USD"), date(2024, 1, 1), date(2024, 1, 3))


@pytest.mark.parametrize(("status", "retryable"), [(429, True), (503, True), (404, False)])
def test_http_failures_are_classified_without_logging_response_secrets(
    monkeypatch, status, retryable
):
    from urllib.error import HTTPError

    from portfolio_research_desk.data_adapters import http_get

    def failure(*_args, **_kwargs):
        raise HTTPError(
            "https://example.test", status, "remote secret body", {"Retry-After": "60"}, None
        )

    monkeypatch.setattr("portfolio_research_desk.data_adapters.urlopen", failure)
    with pytest.raises(ProviderError) as caught:
        http_get("https://example.test", 1)
    assert caught.value.retryable is retryable
    assert caught.value.retry_after == 60
    assert "secret" not in str(caught.value)


def test_yahoo_rate_limit_retries_bounded_times(tmp_path):
    calls, sleeps = [], []

    class YFRateLimitError(Exception):
        pass

    class Limited:
        def history(self, **_kwargs):
            calls.append(1)
            raise YFRateLimitError("quota")

    adapter = YFinanceAdapter(
        tmp_path, RetryPolicy(attempts=2), factory=lambda _: Limited(), sleep=sleeps.append
    )
    with pytest.raises(ProviderError, match="RATE_LIMIT"):
        adapter.fetch(AssetId("US", "XNAS", "AAPL", "USD"), date(2024, 1, 1), date(2024, 1, 3))
    assert len(calls) == 2 and sleeps == [0.5]


@pytest.mark.parametrize(
    ("value", "seconds"),
    [("60", 60), ("Tue, 02 Jan 2024 00:01:00 GMT", 60), ("NaN", 0), ("invalid", 0), ("-1", 0)],
)
def test_retry_after_supports_http_dates_and_bounded_numeric_values(value, seconds):
    assert _retry_after_seconds(value, datetime(2024, 1, 2, tzinfo=UTC)) == seconds


def test_missing_yahoo_metadata_is_a_clear_permanent_failure(tmp_path):
    pd = pytest.importorskip("pandas")

    class MissingMetadata:
        def history(self, **_kwargs):
            return pd.DataFrame({"Close": [10]})

        def get_history_metadata(self):
            return None

    adapter = YFinanceAdapter(tmp_path, factory=lambda _: MissingMetadata())
    with pytest.raises(ProviderError, match="SCHEMA") as caught:
        adapter.fetch(AssetId("US", "XNAS", "AAPL", "USD"), date(2024, 1, 1), date(2024, 1, 3))
    assert caught.value.retryable is False
