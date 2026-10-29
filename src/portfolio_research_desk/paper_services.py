"""User-oriented Paper operations built on the Phase 5 ledger and pure services."""

from portfolio_research_desk.domain import fingerprint
from portfolio_research_desk.paper_inputs import load_paper_input
from portfolio_research_desk.paper_store import PaperAccount, loads


def plan_summary(record):
    plan = record.plan
    return {
        "plan_id": plan.plan_id,
        "status": record.status,
        "plan_hash": fingerprint(plan),
        "data_kind": plan.data_kind,
        "decision_at": plan.decision_at,
        "next_open": plan.session.open_at,
        "target": plan.target,
        "orders": plan.orders,
        "before": plan.before,
        "estimated_after": plan.estimated_after,
        "estimated_fills": plan.estimated_fills,
        "reasons": plan.reasons,
        "rejection_reason": record.reason,
    }


def account_summary(account: PaperAccount):
    view, events = account.audit()
    # Timestamps alone cannot detect a cash movement at the same instant as a
    # valuation. Use event order to keep an old NAV from looking current.
    value_index = 0
    for event in events:
        command = loads(event["payload"])
        if command["kind"] == "VALUE":
            value_index = event["seq"]
        elif command["kind"] == "EXECUTE" and view.plans[command["plan_id"]].status == "SIMULATED":
            value_index = event["seq"]
    stale = any(
        e["seq"] > value_index and loads(e["payload"])["kind"] in {"CASH", "CONVERT", "ACTION"}
        for e in events
    )
    latest = view.valuations[-1] if view.valuations else None
    return {
        "phase": 6,
        "mode": "paper",
        "base_currency": "CAD",
        "credible_real_market_oos": False,
        "cash": view.state.cash,
        "positions": view.state.positions,
        "last_event_at": view.last_at,
        "event_count": view.event_count,
        "head_hash": view.head_hash,
        "commission_cad": view.state.commission_cad,
        "fx_cost_cad": view.state.fx_cost_cad,
        "last_recorded_valuation": latest,
        "valuation_stale": stale or latest is None,
        "plans": [
            {
                "plan_id": k,
                "status": r.status,
                "plan_hash": fingerprint(r.plan),
                "next_open": r.plan.session.open_at,
                "reason": r.reason,
            }
            for k, r in view.plans.items()
        ],
    }


def propose_from_snapshot(account, path, plan_id, top_k=2):
    inputs = load_paper_input(path, "decision")
    view = account.propose(
        inputs.bundle,
        inputs.market,
        inputs.sessions,
        inputs.as_of,
        plan_id,
        top_k,
        target=inputs.target,
    )
    return {
        "phase": 6,
        "mode": "paper",
        "credible_real_market_oos": False,
        "plan": plan_summary(view.plans[plan_id]),
    }


def simulate_from_snapshot(account, path, plan_id, expected_at=None):
    inputs = load_paper_input(path, "execution")
    if expected_at is not None and expected_at != inputs.as_of:
        from portfolio_research_desk.errors import DataError

        raise DataError("--at conflicts with the snapshot's explicit as_of.")
    view = account.execute(plan_id, inputs.as_of, inputs.market)
    return {
        "phase": 6,
        "mode": "paper",
        "credible_real_market_oos": False,
        "plan": plan_summary(view.plans[plan_id]),
        "account": account_summary(account),
    }


def value_from_snapshot(account, path, event_id):
    inputs = load_paper_input(path, "valuation")
    account.append(event_id, {"kind": "VALUE", "at": inputs.as_of, "market": inputs.market})
    return account_summary(account)
