import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

import pytest

from portfolio_research_desk.domain import fingerprint
from portfolio_research_desk.errors import DataError, ExecutionError
from portfolio_research_desk.fx import FXBook
from portfolio_research_desk.paper_sample import example_inputs
from portfolio_research_desk.paper_store import PaperAccount, dumps, loads


def account_case(tmp_path, approved=False):
    x = example_inputs()
    a = PaperAccount.create(tmp_path / "account.sqlite3", x["sessions"][0].open_at)
    v = a.propose(x["bundle"], x["market"], x["sessions"], x["decision_at"], "plan")
    if approved:
        v = a.review("plan", x["review_at"], fingerprint(v.plans["plan"].plan), True)
    return x, a, v


def test_restart_replays_cash_positions_costs_orders_fills_and_valuation(tmp_path):
    x, a, v = account_case(tmp_path, True)
    after = a.execute("plan", x["execution_at"], x["execution_market"])
    restarted = PaperAccount(a.path).load()
    assert restarted == after and restarted.event_count == 4
    assert restarted.plans["plan"].status == "SIMULATED"
    assert len(restarted.plans["plan"].fills) == 3 and restarted.valuations
    before_count = restarted.event_count
    again = PaperAccount(a.path).execute("plan", x["execution_at"], x["execution_market"])
    assert again == after and again.event_count == before_count
    same = a.propose(x["bundle"], x["market"], x["sessions"], x["decision_at"], "plan")
    assert same == after


def test_concurrent_repeated_execution_commits_one_batch(tmp_path):
    x, a, _ = account_case(tmp_path, True)

    def run(_):
        return PaperAccount(a.path).execute("plan", x["execution_at"], x["execution_market"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert results[0] == results[1]
    assert results[0].event_count == 4
    assert len(results[0].plans["plan"].fills) == 3


@pytest.mark.parametrize("kind", ["sqlite", "python"])
def test_failure_after_insert_before_commit_rolls_back_all_economics(tmp_path, monkeypatch, kind):
    x, a, before = account_case(tmp_path, True)

    def fail():
        raise (
            sqlite3.OperationalError("simulated disk full")
            if kind == "sqlite"
            else RuntimeError("interrupted")
        )

    monkeypatch.setattr(a, "_before_commit", fail)
    with pytest.raises((ExecutionError, RuntimeError)):
        a.execute("plan", x["execution_at"], x["execution_market"])
    assert PaperAccount(a.path).load() == before
    result = PaperAccount(a.path).execute("plan", x["execution_at"], x["execution_market"])
    assert result.event_count == before.event_count + 1


def test_abrupt_process_exit_with_uncommitted_insert_recovers_on_restart(tmp_path):
    x, a, before = account_case(tmp_path, True)
    # Child exits without unwinding Python or closing SQLite, after INSERT before COMMIT.
    code = (
        "import os,sys; from pathlib import Path; "
        "from portfolio_research_desk.paper_store import PaperAccount; "
        "from portfolio_research_desk.paper_sample import example_inputs; "
        "a=PaperAccount(Path(sys.argv[1])); x=example_inputs(); "
        "a._before_commit=lambda:os._exit(17); "
        "a.execute('plan',x['execution_at'],x['execution_market'])"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(a.path)], capture_output=True, timeout=20
    )
    assert result.returncode == 17, result.stderr
    assert PaperAccount(a.path).load() == before
    assert (
        PaperAccount(a.path).execute("plan", x["execution_at"], x["execution_market"]).event_count
        == 4
    )


@pytest.mark.parametrize("case", ["quantity", "price", "review_hash", "review_time"])
def test_changed_payload_cannot_reuse_idempotency_key(tmp_path, case):
    x, a, v = account_case(tmp_path, True)
    with pytest.raises(ExecutionError):
        if case in {"quantity", "price"}:
            target = v.plans["plan"].plan.target
            # Same proposal ID with another explicit target is a changed request.
            a.propose(
                x["bundle"], x["market"], x["sessions"], x["decision_at"], "plan", target=target
            )
        elif case == "review_hash":
            a.review("plan", x["review_at"], "wrong", True)
        else:
            a.review(
                "plan",
                x["review_at"] + timedelta(seconds=1),
                fingerprint(v.plans["plan"].plan),
                True,
            )
    assert a.load() == v


@pytest.mark.parametrize(
    "case", ["no_review", "wrong_hash", "late_review", "unknown", "reject_review"]
)
def test_review_is_mandatory_and_exact(tmp_path, case):
    x, a, v = account_case(tmp_path)
    if case == "reject_review":
        v = a.review("plan", x["review_at"], fingerprint(v.plans["plan"].plan), False)
        assert v.plans["plan"].status == "REJECTED"
    with pytest.raises(ExecutionError):
        if case in {"no_review", "reject_review"}:
            a.execute("plan", x["execution_at"], x["execution_market"])
        elif case == "wrong_hash":
            a.review("plan", x["review_at"], "wrong", True)
        elif case == "late_review":
            a.review("plan", x["execution_at"], fingerprint(v.plans["plan"].plan), True)
        else:
            a.review("unknown", x["review_at"], "any", True)
    assert a.load() == v


@pytest.mark.parametrize("case", ["fx", "price", "cash", "future_quote"])
def test_rejected_batch_persists_reason_without_any_partial_fill_or_fee(tmp_path, case):
    x, a, v = account_case(tmp_path, True)
    m = x["execution_market"]
    if case == "fx":
        m = replace(m, fx=FXBook())
    if case == "price":
        m = replace(m, quotes=tuple(replace(q, price=D(9999)) for q in m.quotes))
    if case == "future_quote":
        m = replace(
            m,
            quotes=tuple(
                replace(q, available_at=x["execution_at"] + timedelta(seconds=1)) for q in m.quotes
            ),
        )
    if case == "cash":
        v = a.append(
            "withdraw",
            dict(kind="CASH", at=x["review_at"], currency="CAD", amount=D(-1000), fx=FXBook()),
        )
    after = a.execute("plan", x["execution_at"], m)
    assert after.state == v.state
    assert after.plans["plan"].status == "REJECTED" and after.plans["plan"].reason
    assert not after.plans["plan"].fills
    assert PaperAccount(a.path).load() == after
    assert a.execute("plan", x["execution_at"], m) == after


def test_expired_plan_and_backdated_command(tmp_path):
    x, a, v = account_case(tmp_path)
    v = a.expire("plan", x["execution_at"])
    assert v.plans["plan"].status == "EXPIRED"
    assert a.expire("plan", x["execution_at"]) == v
    with pytest.raises(ExecutionError):
        a.append(
            "late", dict(kind="CASH", at=x["decision_at"], currency="CAD", amount=D(1), fx=FXBook())
        )


def test_cash_conversion_and_corporate_action_event_ids_survive_restart(tmp_path):
    x, a, _ = account_case(tmp_path, True)
    v = a.execute("plan", x["execution_at"], x["execution_market"])
    asset = next(p.asset for p in v.state.positions if p.asset.currency == "CAD")
    action_at = x["execution_at"] + timedelta(seconds=1)
    cmd = dict(
        kind="ACTION",
        at=action_at,
        asset=asset,
        action="DIVIDEND",
        amount=D(".50"),
        available_at=x["decision_at"],
        fx=x["execution_market"].fx,
    )
    first = a.append("dividend-1", cmd)
    assert first.state.balances()["CAD"] - v.state.balances()["CAD"] == D("14.50")
    assert PaperAccount(a.path).append("dividend-1", cmd) == first
    cmd = dict(
        kind="CONVERT",
        at=action_at,
        source="CAD",
        amount=D(10),
        fx=x["execution_market"].fx,
    )
    converted = a.append("convert-1", cmd)
    assert PaperAccount(a.path).append("convert-1", cmd) == converted
    assert converted.state.balances()["USD"] == 10
    cmd = dict(kind="CASH", at=action_at, currency="CAD", amount=D(20), fx=FXBook())
    flow = a.append("flow-1", cmd)
    assert a.append("flow-1", cmd) == flow
    assert flow.state.net_contributions_cad == D(3020)


@pytest.mark.parametrize(
    "corruption", ["payload", "hash", "sequence", "version", "foreign_database"]
)
def test_corrupt_or_foreign_database_fails_closed(tmp_path, corruption):
    _, a, _ = account_case(tmp_path)
    with sqlite3.connect(a.path) as db:
        if corruption == "payload":
            db.execute("UPDATE events SET payload='{}' WHERE seq=2")
        elif corruption == "hash":
            db.execute("UPDATE events SET previous_hash='wrong' WHERE seq=2")
        elif corruption == "sequence":
            db.execute("UPDATE events SET seq=7 WHERE seq=2")
        elif corruption == "version":
            db.execute("PRAGMA user_version=99")
        else:
            db.execute("PRAGMA application_id=0")
    with pytest.raises(ExecutionError):
        a.load()


def test_missing_db_and_existing_account_are_not_overwritten(tmp_path):
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(ExecutionError):
        PaperAccount(path).load()
    assert not path.exists()
    x, a, v = account_case(tmp_path)
    with pytest.raises(ExecutionError):
        PaperAccount.create(a.path, x["decision_at"])
    assert a.load() == v


def test_typed_codec_is_exact_and_does_not_load_arbitrary_classes():
    x = example_inputs()
    assert loads(dumps(x)) == x
    with pytest.raises(DataError):
        loads('{"type":"eval","fields":{}}')
    with pytest.raises(DataError):
        loads(json.dumps({"type": "CADState", "fields": {}}))


def test_tail_deletion_is_detected_by_atomically_persisted_head(tmp_path):
    _, account, _ = account_case(tmp_path)
    with sqlite3.connect(account.path) as db:
        db.execute("DELETE FROM events WHERE seq=2")
    with pytest.raises(ExecutionError, match="tail/head"):
        account.load()


def test_replay_algorithm_drift_fails_closed(tmp_path, monkeypatch):
    from portfolio_research_desk import paper_store

    _, account, _ = account_case(tmp_path)
    original = paper_store.apply_command

    def changed(view, command):
        result = original(view, command)
        return replace(result, state=replace(result.state, realized_pnl_cad=D(999)))

    monkeypatch.setattr(paper_store, "apply_command", changed)
    with pytest.raises(ExecutionError, match="replay result changed"):
        account.load()


def test_wrong_events_table_shape_is_clean_error(tmp_path):
    _, account, _ = account_case(tmp_path)
    with sqlite3.connect(account.path) as db:
        db.execute("ALTER TABLE events DROP COLUMN result_hash")
    with pytest.raises(ExecutionError, match="Cannot read paper ledger"):
        account.load()


def test_wrong_execution_timestamp_cannot_advance_ledger_or_consume_retry_key(tmp_path):
    x, account, before = account_case(tmp_path, True)
    with pytest.raises(ExecutionError, match="Invalid execution timestamp"):
        account.execute("plan", x["execution_at"] + timedelta(days=100), x["execution_market"])
    assert account.load() == before
    assert (
        account.execute("plan", x["execution_at"], x["execution_market"]).plans["plan"].status
        == "SIMULATED"
    )
