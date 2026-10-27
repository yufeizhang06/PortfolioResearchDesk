import hashlib
from importlib.resources import files

import pytest

from portfolio_research_desk.errors import SampleError
from portfolio_research_desk.sample import summarize_sample


def test_sample_is_deterministic_and_explicitly_synthetic():
    first = summarize_sample()
    assert first == summarize_sample()
    assert first["synthetic"] is True
    assert first["rows"] == 9
    assert first["symbols"] == ["SYN_A", "SYN_B", "SYN_C"]
    assert first["session_start"] == "2024-01-02"
    assert first["session_end"] == "2024-01-04"
    assert first["currency"] == "USD"
    assert first["adjusted"] is False
    raw = files("portfolio_research_desk").joinpath("resources/synthetic_prices.csv").read_bytes()
    assert first["sha256"] == hashlib.sha256(raw).hexdigest()
    assert first["limitations"]
    assert not {"returns", "sharpe", "orders", "signals"} & first.keys()


@pytest.fixture
def sample_copy(tmp_path, monkeypatch):
    resource_dir = tmp_path / "resources"
    resource_dir.mkdir()
    path = resource_dir / "synthetic_prices.csv"
    path.write_bytes(
        files("portfolio_research_desk").joinpath("resources/synthetic_prices.csv").read_bytes()
    )
    monkeypatch.setattr("portfolio_research_desk.sample.files", lambda _: tmp_path)
    return path


@pytest.mark.parametrize(
    ("before", "after", "error"),
    [
        (",100.00,", ",0,", "finite and positive"),
        (",100.00,", ",NaN,", "finite and positive"),
        (",102.00,99.00,", ",98.00,99.00,", "OHLC bounds"),
        (",1000,USD,", ",0,USD,", "volume"),
        (",USD,", ",CAD,", "identity/source/currency"),
        ("2024-01-02T21:01:00Z", "2024-01-02T20:59:00Z", "availability"),
        ("2024-01-02T21:01:00Z", "2024-01-02T21:01:00", "timezone-aware UTC"),
        ("2024-01-02T21:01:00Z", "2024-01-02T21:01:00+01:00", "timezone-aware UTC"),
        (",100.00,", ",invalid,", "Cannot read valid"),
        ("market,exchange", "bad,exchange", "unexpected columns"),
    ],
)
def test_corrupt_sample_is_rejected(sample_copy, before, after, error):
    sample_copy.write_text(
        sample_copy.read_text(encoding="utf-8").replace(before, after, 1), encoding="utf-8"
    )
    with pytest.raises(SampleError, match=error):
        summarize_sample()


@pytest.mark.parametrize("corruption", ["empty", "duplicate", "short", "long"])
def test_empty_duplicate_and_malformed_rows(sample_copy, corruption):
    lines = sample_copy.read_text(encoding="utf-8").splitlines()
    if corruption == "empty":
        lines = lines[:1]
    elif corruption == "duplicate":
        lines.append(lines[1])
    elif corruption == "short":
        lines[1] = lines[1].rsplit(",", 1)[0]
    else:
        lines[1] += ",unexpected"
    sample_copy.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(SampleError):
        summarize_sample()


def test_missing_sample_is_reported(sample_copy):
    sample_copy.unlink()
    with pytest.raises(SampleError, match="Cannot read valid"):
        summarize_sample()
