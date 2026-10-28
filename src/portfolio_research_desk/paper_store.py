"""Single-account SQLite event ledger, deterministic replay and atomic idempotence."""

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from portfolio_research_desk import domain, fx, paper_domain, portfolio_risk, rebalancing
from portfolio_research_desk.domain import fingerprint, require_utc
from portfolio_research_desk.errors import DataError, ExecutionError, ProjectError
from portfolio_research_desk.paper_domain import CADState, Costs, accounting, money
from portfolio_research_desk.paper_execution import (
    cash_flow,
    convert_cash,
    corporate_action,
    simulate_plan,
)
from portfolio_research_desk.portfolio_risk import RiskLimits, value_portfolio
from portfolio_research_desk.rebalancing import propose_rebalance

_TYPES = {
    t.__name__: t
    for module in (domain, fx, paper_domain, portfolio_risk, rebalancing)
    for t in vars(module).values()
    if isinstance(t, type) and is_dataclass(t)
}
_APP_ID = 0x50524435


def wire(value):
    """Closed typed JSON codec; no pickle or executable object deserialization."""
    if is_dataclass(value):
        return {
            "type": type(value).__name__,
            "fields": {f.name: wire(getattr(value, f.name)) for f in fields(value)},
        }
    if isinstance(value, Decimal):
        return {"decimal": str(value)}
    if isinstance(value, datetime):
        return {"datetime": value.isoformat()}
    if isinstance(value, date):
        return {"date": value.isoformat()}
    if isinstance(value, tuple):
        return {"tuple": [wire(v) for v in value]}
    if isinstance(value, dict):
        return {"dict": {k: wire(v) for k, v in value.items()}}
    if value is None or type(value) in (str, bool, int):
        return value
    raise DataError("Unsupported ledger input type.")


def unwire(value):
    if not isinstance(value, dict):
        if value is None or type(value) in (str, bool, int):
            return value
        raise DataError("Invalid ledger scalar.")
    keys = set(value)
    if keys == {"type", "fields"} and value["type"] in _TYPES:
        cls = _TYPES[value["type"]]
        if set(value["fields"]) != {f.name for f in fields(cls)}:
            raise DataError("Invalid versioned ledger contract fields.")
        return cls(**{k: unwire(v) for k, v in value["fields"].items()})
    if keys == {"decimal"}:
        return Decimal(value["decimal"])
    if keys == {"datetime"}:
        return datetime.fromisoformat(value["datetime"])
    if keys == {"date"}:
        return date.fromisoformat(value["date"])
    if keys == {"tuple"}:
        return tuple(unwire(v) for v in value["tuple"])
    if keys == {"dict"}:
        return {k: unwire(v) for k, v in value["dict"].items()}
    raise DataError("Unrecognized ledger JSON contract.")


def dumps(value):
    return json.dumps(wire(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def loads(text):
    try:
        return unwire(json.loads(text))
    except (ValueError, TypeError, KeyError, ArithmeticError, AttributeError) as exc:
        raise DataError("Invalid typed ledger JSON.") from exc


@dataclass(frozen=True)
class PlanRecord:
    plan: object
    status: str = "PENDING_REVIEW"
    reviewed_at: datetime | None = None
    reason: str = ""
    fills: tuple = ()
    valuation: object = None


@dataclass(frozen=True)
class AccountView:
    state: CADState
    limits: RiskLimits
    costs: Costs
    last_at: datetime
    plans: dict
    valuations: tuple = ()
    conversions: tuple = ()
    event_count: int = 0
    head_hash: str = ""


def result_fingerprint(view):
    return fingerprint(replace(view, event_count=0, head_hash=""))


@accounting
def apply_command(view, command):
    """Recompute ledger state from original inputs, including rejected executions."""
    schemas = {
        "INIT": {"initial_cash", "limits", "costs"},
        "PROPOSE": {"inputs"},
        "REVIEW": {"plan_id", "plan_hash", "approve", "reason"},
        "EXECUTE": {"plan_id", "market"},
        "EXPIRE": {"plan_id"},
        "CASH": {"currency", "amount", "fx"},
        "CONVERT": {"source", "amount", "fx"},
        "ACTION": {"asset", "action", "amount", "available_at", "fx"},
        "VALUE": {"market"},
    }
    if (
        not isinstance(command, dict)
        or not isinstance(command.get("kind"), str)
        or command["kind"] not in schemas
        or set(command) != schemas[command["kind"]] | {"kind", "at"}
    ):
        raise DataError("Ledger command has unknown/missing fields or operation.")
    kind, at = command["kind"], command["at"]
    require_utc(at)
    if "market" in command and not isinstance(command["market"], portfolio_risk.MarketSnapshot):
        raise DataError("Ledger operation requires a MarketSnapshot.")
    if "fx" in command and not isinstance(command["fx"], fx.FXBook):
        raise DataError("Ledger operation requires an FXBook.")
    if "plan_id" in command and (not isinstance(command["plan_id"], str) or not command["plan_id"]):
        raise DataError("Plan ID must be a nonempty string.")
    if view is None:
        if kind != "INIT":
            raise ExecutionError("Ledger must begin with account initialization.")
        money(command["initial_cash"], "initial CAD capital", positive=True)
        if not isinstance(command["limits"], RiskLimits) or not isinstance(command["costs"], Costs):
            raise DataError("Account requires explicit validated risk and cost settings.")
        state = CADState(
            at,
            (("CAD", command["initial_cash"]), ("USD", Decimal("0.00"))),
            net_contributions_cad=command["initial_cash"],
        )
        return AccountView(state, command["limits"], command["costs"], at, {})
    if kind == "INIT" or at < view.last_at:
        raise ExecutionError("Duplicate initialization or backdated ledger command.")
    state, plans = view.state, dict(view.plans)
    updated = replace(view, last_at=at, plans=plans)
    if kind == "PROPOSE":
        kwargs = command["inputs"]
        proposal_keys = {
            "bundle",
            "market",
            "sessions",
            "decision_at",
            "plan_id",
            "top_k",
            "target",
            "mode",
            "limits",
            "costs",
        }
        if not isinstance(kwargs, dict) or set(kwargs) != proposal_keys:
            raise DataError("Invalid versioned proposal inputs.")
        if kwargs["limits"] != view.limits or kwargs["costs"] != view.costs:
            raise DataError("Plan must use this account's immutable risk/cost configuration.")
        if at != kwargs["decision_at"] or kwargs["mode"] != "paper":
            raise ExecutionError("Paper storage refuses historical/backtest plans.")
        plan = propose_rebalance(state, **kwargs)
        if plan.plan_id in plans:
            raise ExecutionError("Plan ID already exists.")
        plans[plan.plan_id] = PlanRecord(plan)
    elif kind in {"REVIEW", "EXECUTE", "EXPIRE"}:
        record = plans.get(command["plan_id"])
        if record is None:
            raise ExecutionError("Unknown paper plan.")
        if kind == "REVIEW":
            if (
                record.status != "PENDING_REVIEW"
                or not record.plan.decision_at <= at < record.plan.session.open_at
            ):
                raise ExecutionError(
                    "Only an unexpired pending plan can be reviewed before execution."
                )
            if (
                command["plan_hash"] != fingerprint(record.plan)
                or type(command["approve"]) is not bool
            ):
                raise ExecutionError(
                    "Review must reference the exact plan hash and explicit approval."
                )
            plans[command["plan_id"]] = replace(
                record,
                reviewed_at=at,
                status="APPROVED" if command["approve"] else "REJECTED",
                reason=command["reason"],
            )
        elif kind == "EXPIRE":
            if (
                record.status not in {"PENDING_REVIEW", "APPROVED"}
                or at < record.plan.session.open_at
            ):
                raise ExecutionError("Only an outstanding plan at/past its session may expire.")
            plans[command["plan_id"]] = replace(
                record, status="EXPIRED", reason="MISSED_PLANNED_OPEN"
            )
        else:
            if record.status != "APPROVED" or record.reviewed_at >= at:
                raise ExecutionError("Explicit review must precede simulated execution.")
            if at != record.plan.session.open_at:
                raise ExecutionError(
                    "Invalid execution timestamp; use the planned next session open."
                )
            try:
                state, fills, valuation = simulate_plan(state, record.plan, command["market"], at)
                plans[command["plan_id"]] = replace(
                    record, status="SIMULATED", fills=fills, valuation=valuation
                )
                updated = replace(updated, valuations=updated.valuations + (valuation,))
            except (DataError, ExecutionError) as exc:
                plans[command["plan_id"]] = replace(record, status="REJECTED", reason=str(exc))
    elif kind == "CASH":
        state = cash_flow(
            state, command["currency"], command["amount"], at, command["fx"], view.limits
        )
    elif kind == "CONVERT":
        state, conversion = convert_cash(
            state, command["source"], command["amount"], command["fx"], at, view.costs, view.limits
        )
        updated = replace(updated, conversions=updated.conversions + (conversion,))
    elif kind == "ACTION":
        state = corporate_action(
            state,
            command["asset"],
            command["action"],
            command["amount"],
            at,
            command["available_at"],
            command["fx"],
            view.limits,
        )
    elif kind == "VALUE":
        valuation = value_portfolio(state, command["market"], at, view.limits)
        updated = replace(updated, valuations=updated.valuations + (valuation,))
    else:
        raise ExecutionError("Unknown ledger operation.")
    return replace(updated, state=state)


class PaperAccount:
    """One local file per virtual account. Every mutation is one IMMEDIATE transaction."""

    def __init__(self, path: Path):
        self.path = Path(path).resolve()

    @classmethod
    def create(cls, path, at, initial_cash=Decimal("3000.00"), limits=None, costs=None):
        limits = limits if limits is not None else RiskLimits()
        costs = costs if costs is not None else Costs()
        account = cls(path)
        command = dict(kind="INIT", at=at, initial_cash=initial_cash, limits=limits, costs=costs)
        initial = apply_command(None, command)  # Validate before creating any file.
        try:
            account.path.parent.mkdir(parents=True, exist_ok=True)
            with account.path.open("xb"):
                pass
            with closing(sqlite3.connect(account.path, isolation_level=None)) as db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("BEGIN EXCLUSIVE")
                db.execute(f"PRAGMA application_id={_APP_ID}")
                db.execute("PRAGMA user_version=1")
                db.execute(
                    "CREATE TABLE events (seq INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, "
                    "payload TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL, "
                    "result_hash TEXT NOT NULL)"
                )
                db.execute(
                    "CREATE TABLE ledger_head (id INTEGER PRIMARY KEY CHECK(id=1), "
                    "event_count INTEGER NOT NULL, event_hash TEXT NOT NULL)"
                )
                payload = dumps(command)
                result_hash = result_fingerprint(initial)
                digest = fingerprint([1, "init", payload, "", result_hash])
                db.execute(
                    "INSERT INTO events VALUES (1, ?, ?, ?, ?, ?)",
                    ("init", payload, "", digest, result_hash),
                )
                db.execute("INSERT INTO ledger_head VALUES (1, 1, ?)", (digest,))
                db.commit()
        except (OSError, sqlite3.Error) as exc:
            raise ExecutionError(
                "Cannot create paper account; existing files are never overwritten."
            ) from exc
        return account

    def _connect(self):
        try:
            db = sqlite3.connect(
                self.path.as_uri() + "?mode=rw", uri=True, timeout=5, isolation_level=None
            )
            if (
                db.execute("PRAGMA application_id").fetchone()[0] != _APP_ID
                or db.execute("PRAGMA user_version").fetchone()[0] != 1
                or db.execute("PRAGMA quick_check").fetchone()[0] != "ok"
            ):
                db.close()
                raise ExecutionError(
                    "Unsupported/corrupt paper database; refusing to repair silently."
                )
            db.execute("PRAGMA synchronous=FULL")
            return db
        except sqlite3.Error as exc:
            raise ExecutionError("Cannot open verified paper account.") from exc

    @staticmethod
    def _replay(db):
        view, previous, expected = None, "", 1
        for seq, event_id, payload, prior, digest, result_hash in db.execute(
            "SELECT seq, event_id, payload, previous_hash, event_hash, result_hash "
            "FROM events ORDER BY seq"
        ):
            if (
                seq != expected
                or prior != previous
                or digest != fingerprint([seq, event_id, payload, prior, result_hash])
            ):
                raise ExecutionError("Paper ledger hash chain/sequence is corrupt.")
            try:
                view = apply_command(view, loads(payload))
            except (
                ProjectError,
                ValueError,
                TypeError,
                KeyError,
                ArithmeticError,
                AttributeError,
            ) as exc:
                raise ExecutionError(
                    "Paper ledger replay failed; no state was overwritten."
                ) from exc
            if result_fingerprint(view) != result_hash:
                raise ExecutionError(
                    "Ledger replay result changed; explicit versioned migration required."
                )
            previous, expected = digest, expected + 1
        if view is None:
            raise ExecutionError("Paper account has no initialization event.")
        if db.execute("SELECT event_count, event_hash FROM ledger_head WHERE id=1").fetchone() != (
            expected - 1,
            previous,
        ):
            raise ExecutionError("Paper ledger tail/head mismatch; refusing truncated state.")
        return replace(view, event_count=expected - 1, head_hash=previous)

    def load(self):
        db = self._connect()
        try:
            db.execute("BEGIN")
            return self._replay(db)
        except sqlite3.Error as exc:
            raise ExecutionError("Cannot read paper ledger.") from exc
        finally:
            db.close()

    def audit(self):
        """Read state and original events from one consistent database snapshot."""
        db = self._connect()
        try:
            db.execute("BEGIN")
            view = self._replay(db)
            events = tuple(
                dict(
                    zip(
                        (
                            "seq",
                            "event_id",
                            "payload",
                            "previous_hash",
                            "event_hash",
                            "result_hash",
                        ),
                        row,
                        strict=True,
                    )
                )
                for row in db.execute("SELECT * FROM events ORDER BY seq")
            )
            return view, events
        except sqlite3.Error as exc:
            raise ExecutionError("Cannot export paper ledger.") from exc
        finally:
            db.close()

    def append(self, event_id, command):
        if not isinstance(event_id, str) or not event_id or event_id == "init":
            raise ExecutionError("A unique non-initialization event ID is required.")
        payload = dumps(command)
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            view = self._replay(db)
            existing = db.execute(
                "SELECT payload FROM events WHERE event_id=?", (event_id,)
            ).fetchone()
            if existing:
                if existing[0] != payload:
                    raise ExecutionError(
                        "Idempotency ID collision: changed inputs cannot reuse an event ID."
                    )
                db.rollback()
                return view
            updated = apply_command(view, command)
            seq = view.event_count + 1
            result_hash = result_fingerprint(updated)
            digest = fingerprint([seq, event_id, payload, view.head_hash, result_hash])
            db.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                (seq, event_id, payload, view.head_hash, digest, result_hash),
            )
            db.execute(
                "UPDATE ledger_head SET event_count=?, event_hash=? WHERE id=1", (seq, digest)
            )
            self._before_commit()
            db.commit()
            return replace(updated, event_count=seq, head_hash=digest)
        except sqlite3.Error as exc:
            db.rollback()
            raise ExecutionError("Paper ledger transaction failed; operation rolled back.") from exc
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _before_commit(self):
        """Private fault injection seam; production does nothing."""

    def propose(self, bundle, market, sessions, decision_at, plan_id, top_k=5, target=None):
        self._plan_id(plan_id)
        view = self.load()
        inputs = dict(
            bundle=bundle,
            market=market,
            sessions=sessions,
            decision_at=decision_at,
            plan_id=plan_id,
            top_k=top_k,
            target=target,
            mode="paper",
            limits=view.limits,
            costs=view.costs,
        )
        return self.append(
            "propose:" + plan_id, dict(kind="PROPOSE", at=decision_at, inputs=inputs)
        )

    def review(self, plan_id, at, plan_hash, approve, reason="Human paper-plan review"):
        self._plan_id(plan_id)
        return self.append(
            "review:" + plan_id,
            dict(
                kind="REVIEW",
                at=at,
                plan_id=plan_id,
                plan_hash=plan_hash,
                approve=approve,
                reason=reason,
            ),
        )

    def execute(self, plan_id, at, market):
        self._plan_id(plan_id)
        return self.append(
            "execute:" + plan_id, dict(kind="EXECUTE", at=at, plan_id=plan_id, market=market)
        )

    def expire(self, plan_id, at):
        self._plan_id(plan_id)
        return self.append("expire:" + plan_id, dict(kind="EXPIRE", at=at, plan_id=plan_id))

    @staticmethod
    def _plan_id(value):
        if not isinstance(value, str) or not value:
            raise DataError("Plan ID must be a nonempty string.")
