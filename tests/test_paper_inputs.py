"""Readable transport remains a strict adapter to the audited Paper contracts."""

import copy
import json
from dataclasses import replace
from decimal import Decimal

import pytest

from portfolio_research_desk.errors import DataError, ExecutionError
from portfolio_research_desk.paper_inputs import load_paper_input, parse_paper_input
from portfolio_research_desk.paper_services import propose_from_snapshot
from portfolio_research_desk.paper_store import PaperAccount
from portfolio_research_desk.workflow_fixtures import delivery_inputs, paper_documents


@pytest.mark.parametrize(
    "name,purpose", [("decision", "decision"), ("opening", "execution"), ("closing", "valuation")]
)
def test_readable_inputs_match_typed_fixture_contracts(tmp_path, name, purpose):
    x = delivery_inputs()
    doc = paper_documents()[name]
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    parsed = load_paper_input(path, purpose)
    expected = x[{"decision": "decision", "opening": "opening", "closing": "closing"}[name]]
    assert parsed.market.quotes == tuple(replace(q, source=doc["source"]) for q in expected.quotes)
    assert parsed.market.fx.rates[0].cad_per_usd == expected.fx.rates[0].cad_per_usd
    assert parsed.data_kind == "synthetic"
    if name == "decision":
        assert parsed.bundle.signals == x["bundle"].signals
        assert parsed.bundle.universe.assets == x["bundle"].universe.assets
        assert parsed.sessions == x["sessions"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("schema_version", 5),
        ("purpose", {}),
        ("purpose", "backtest"),
        ("data_kind", {}),
        ("data_kind", "real"),
        ("source", None),
        ("as_of", "2024-01-04"),
        ("as_of", {}),
        ("prices", {}),
        ("sectors", None),
        ("fx", False),
    ],
)
def test_invalid_top_level_fields_fail_cleanly(field, value):
    doc = paper_documents()["decision"]
    doc[field] = value
    with pytest.raises(DataError):
        parse_paper_input(doc)


@pytest.mark.parametrize(
    "section,field,value",
    [
        ("prices", "price", "NaN"),
        ("prices", "price", "0"),
        ("prices", "price", "1.001"),
        ("prices", "price", {}),
        ("prices", "price", True),
        ("prices", "asset", []),
        ("prices", "asset", "AAPL"),
        ("prices", "kind", {}),
        ("prices", "adjusted", True),
        ("prices", "volume", False),
        ("prices", "tradable", "yes"),
        ("fx", "cad_per_usd", "Infinity"),
        ("fx", "cad_per_usd", -1),
        ("fx", "available_at", "yesterday"),
        ("sectors", "name", {}),
        ("signals", "score", []),
        ("signals", "score", "NaN"),
        ("sessions", "date", {}),
        ("sessions", "date", "2024-99-01"),
    ],
)
def test_invalid_nested_values_never_escape_as_type_errors(section, field, value):
    doc = paper_documents()["decision"]
    doc[section][0][field] = value
    with pytest.raises((DataError, ExecutionError)):
        parse_paper_input(doc)


@pytest.mark.parametrize(
    "case",
    [
        "unknown_root",
        "unknown_row",
        "late_price",
        "late_signal",
        "late_universe",
        "duplicate_price",
        "duplicate_signal",
        "fake_pit",
        "relabel",
    ],
)
def test_provenance_and_temporal_boundaries(case):
    doc = paper_documents()["decision"]
    if case == "unknown_root":
        doc["automatic_broker"] = True
    elif case == "unknown_row":
        doc["prices"][0]["commission"] = 0
    elif case == "late_price":
        doc["prices"][0]["available_at"] = "2024-01-05T00:00:00Z"
    elif case == "late_signal":
        doc["signals"][0]["available_at"] = "2024-01-05T00:00:00Z"
    elif case == "late_universe":
        doc["universe"]["available_at"] = "2024-01-05T00:00:00Z"
    elif case == "duplicate_price":
        doc["prices"].append(copy.deepcopy(doc["prices"][0]))
    elif case == "duplicate_signal":
        doc["signals"].append(copy.deepcopy(doc["signals"][0]))
    elif case == "fake_pit":
        doc["universe"]["membership_type"] = "point_in_time"
    else:
        doc["data_kind"] = "paper_observed"
    with pytest.raises((DataError, ExecutionError)):
        parse_paper_input(doc)


def test_purpose_cannot_be_used_at_another_boundary():
    with pytest.raises(DataError, match="Expected a execution"):
        parse_paper_input(paper_documents()["decision"], "execution")


def test_forward_paper_observations_are_explicit_and_not_historical_certification():
    doc = paper_documents()["decision"]
    doc["data_kind"] = "paper_observed"
    raw = (
        json.dumps(doc)
        .replace("SYN_A", "EXAMPLE_A")
        .replace("SYN_B", "EXAMPLE_B")
        .replace("SYN_C", "EXAMPLE_C")
    )
    parsed = parse_paper_input(json.loads(raw))
    assert parsed.bundle.universe.synthetic is False
    assert parsed.bundle.universe.point_in_time_verified is False
    with pytest.raises(DataError, match="historical PIT"):
        parsed.bundle.validate(parsed.as_of, "backtest")


@pytest.mark.parametrize("bad", [True, "-0.1", "1.1", "NaN"])
def test_bad_explicit_target_weights_are_rejected(bad):
    doc = paper_documents()["decision"]
    doc["target"] = {
        "weights": [{"asset": doc["signals"][0]["asset"], "weight": bad}],
        "cash_weight": "0.8",
    }
    with pytest.raises((DataError, ExecutionError)):
        parse_paper_input(doc)


def test_explicit_target_uses_existing_account_risk_checks(tmp_path):
    x = delivery_inputs()
    doc = paper_documents()["decision"]
    doc["target"] = {
        "weights": [{"asset": doc["signals"][0]["asset"], "weight": "0.18"}],
        "cash_weight": "0.82",
    }
    path = tmp_path / "decision.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    account = PaperAccount.create(tmp_path / "account.sqlite3", x["dataset"].sessions[0].open_at)
    result = propose_from_snapshot(account, path, "target")
    assert result["plan"]["target"].cash_weight == Decimal(".82")
    assert result["plan"]["status"] == "PENDING_REVIEW"
    doc["target"]["weights"][0]["weight"] = "0.9"
    doc["target"]["cash_weight"] = "0.1"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ExecutionError, match="risk limits"):
        propose_from_snapshot(account, path, "unsafe")
    assert account.load().event_count == 2
