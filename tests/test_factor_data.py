import io
import zipfile
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D

import pytest

from portfolio_research_desk.domain import jsonable
from portfolio_research_desk.errors import DataError
from portfolio_research_desk.factor_data import (
    FactorData,
    FactorRow,
    FrenchAdapter,
    combine_factors,
    factors_from_dict,
    parse_french_table,
    require_factor_signal_use,
)

STAMP = datetime(2024, 6, 1, tzinfo=UTC)
THREE = (
    b"French format test\n,Mkt-RF,SMB,HML,RF\n20240102,1.25,-0.5,0.0,0.02\n"
    b"20240103,-99.99,-999,,0.01\n\nAnnual Factors: January-December\n2024,99,99,99,99\n"
)
MOM = b"French format test\n,Mom   \n20240102,2.5\n20240103,-99.99\n"


def test_percent_to_decimal_rf_missing_and_annual_table_is_not_consumed():
    rows = parse_french_table(THREE, "daily")
    assert len(rows) == 2
    assert rows[date(2024, 1, 2)] == (D(".0125"), D("-.005"), D("0"), D(".0002"))
    assert rows[date(2024, 1, 3)] == (None, None, None, D(".0001"))
    combined = combine_factors(THREE, MOM, "daily", STAMP, "injected test source", True)
    assert combined.rows[0].mom == D(".025")
    assert combined.rows[1].mom is None
    assert factors_from_dict(jsonable(combined)) == combined
    assert combined.unit == "decimal_return"


def test_monthly_labels_and_frequency_mismatch():
    monthly = b",Mkt-RF,SMB,HML,RF\n202402,1,2,3,0.1\n"
    assert list(parse_french_table(monthly, "monthly")) == [date(2024, 2, 29)]
    with pytest.raises(DataError, match="frequency"):
        parse_french_table(monthly, "daily")
    with pytest.raises(DataError, match="frequency"):
        parse_french_table(THREE, "monthly")


@pytest.mark.parametrize(
    "content",
    [
        b"<html>error</html>",
        b",RF,SMB,HML,Mkt-RF\n20240102,1,2,3,4\n",
        b",Mkt-RF,SMB,HML,RF\n20240102,1,2,3\n",
        b",Mkt-RF,SMB,HML,RF\n20240102,1,2,3,4\n20240102,2,3,4,5\n",
        b",Mkt-RF,SMB,HML,RF\n20240230,1,2,3,4\n",
        b",Mkt-RF,SMB,HML,RF\n20240102,NaN,2,3,4\n",
        b",Mkt-RF,SMB,HML,RF\n20240102,inf,2,3,4\n",
        b",Mkt-RF,SMB,HML,RF\n20240102,garbage,2,3,4\n",
    ],
)
def test_malformed_factor_sources_fail_closed(content):
    with pytest.raises(DataError):
        parse_french_table(content, "daily")


def test_zip_parser_never_extracts_and_rejects_ambiguous_members():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("../input.csv", THREE)
    assert parse_french_table(stream.getvalue(), "daily") == parse_french_table(THREE, "daily")
    with zipfile.ZipFile(stream, "a") as archive:
        archive.writestr("other.csv", THREE)
    with pytest.raises(DataError, match="one bounded"):
        parse_french_table(stream.getvalue(), "daily")
    with pytest.raises(DataError, match="ZIP"):
        parse_french_table(b"PKbroken", "daily")


def test_french_cache_offline_ttl_and_no_synthetic_fallback(tmp_path):
    calls = []

    def transport(url, timeout):
        calls.append((url, timeout))
        return MOM if "Momentum" in url else THREE

    adapter = FrenchAdapter(tmp_path, transport, lambda: STAMP)
    data, event = adapter.fetch()
    assert len(calls) == 2 and not event["hit"]
    again, event = adapter.fetch(offline=True)
    assert again == data and event["hit"] and len(calls) == 2
    late = FrenchAdapter(tmp_path, transport, lambda: STAMP + timedelta(days=2))
    with pytest.raises(DataError, match="Offline"):
        late.fetch(offline=True)
    assert late.fetch(offline=True, allow_stale=True)[1]["stale"]
    with pytest.raises(DataError, match="Offline"):
        adapter.fetch("monthly", offline=True)
    with pytest.raises(DataError, match="Offline"):
        adapter.fetch(offline=True, refresh=True)
    assert len(calls) == 2


def test_unverified_factor_vintage_never_enters_signal_even_after_retrieval():
    data = combine_factors(THREE, MOM, "daily", STAMP, "injected", True)
    with pytest.raises(DataError, match="unavailable"):
        require_factor_signal_use(data, STAMP - timedelta(days=1))
    with pytest.raises(DataError, match="descriptive"):
        require_factor_signal_use(data, STAMP + timedelta(days=1))
    with pytest.raises(DataError):
        replace(data, unit="percent")
    with pytest.raises(DataError):
        replace(data, rows=tuple(reversed(data.rows)))
    with pytest.raises(DataError):
        FactorData(
            "daily",
            (FactorRow(date(2025, 1, 1), D(1), D(1), D(1), D(0), D(1)),),
            "injected",
            STAMP,
            {},
            True,
        )
