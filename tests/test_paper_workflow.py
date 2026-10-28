import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from fractions import Fraction
from pathlib import Path

import pytest

from portfolio_research_desk.cli import main
from portfolio_research_desk.domain import PriceBar, fingerprint, jsonable
from portfolio_research_desk.errors import ConfigError, DataError, ReportError
from portfolio_research_desk.fx import FXBook, FXRate
from portfolio_research_desk.paper_config import load_paper_config
from portfolio_research_desk.paper_reporting import read_native, write_native, write_paper_report
from portfolio_research_desk.paper_sample import example_inputs
from portfolio_research_desk.paper_store import PaperAccount
from portfolio_research_desk.rebalancing import bundle_from_ml_predictions
from portfolio_research_desk.signals import momentum_signals


def test_packaged_and_editable_configs_match():
    assert load_paper_config() == load_paper_config(Path("configs/example_paper.toml"))
    assert load_paper_config().snapshot()["base_currency"] == "CAD"


def test_research_to_cad_revaluation_and_full_account_restart(tmp_path):
    """One acceptance path across existing research, planning, ledger and reports."""
    x = example_inputs()
    session = x["sessions"][0]
    bars = []
    for quote, prior in zip(x["market"].quotes, ("9.50", "19.00", "24.00"), strict=True):
        for lag, price in ((3, D(prior)), (0, quote.price)):
            day = session.session_date - timedelta(days=lag)
            opened, closed = (
                session.open_at - timedelta(days=lag),
                session.close_at - timedelta(days=lag),
            )
            bars.append(
                PriceBar(
                    quote.asset,
                    day,
                    opened,
                    closed,
                    closed,
                    closed,
                    price,
                    price,
                    price,
                    price,
                    100000,
                    True,
                    source="synthetic_phase5_acceptance",
                )
            )
    signals = momentum_signals(tuple(bars), x["bundle"].universe.assets, x["decision_at"], 1)
    bundle = replace(x["bundle"], signals=signals, source="momentum_1_session_synthetic")
    account = PaperAccount.create(tmp_path / "account.sqlite3", session.open_at)
    view = account.propose(bundle, x["market"], x["sessions"], x["decision_at"], "acceptance")
    plan = view.plans["acceptance"].plan
    assert view.plans["acceptance"].status == "PENDING_REVIEW"
    assert plan.target.cash_weight == D("0.40")
    assert sum((w for _, w in plan.target.weights), D(0)) + plan.target.cash_weight == 1
    account.review(
        "acceptance",
        x["review_at"],
        fingerprint(plan),
        True,
        "User-authorized synthetic acceptance review",
    )
    executed = account.execute("acceptance", x["execution_at"], x["execution_market"])
    assert executed.plans["acceptance"].valuation.nav_cad == D("2994.48")
    assert len(executed.plans["acceptance"].fills) == 3
    assert account.execute("acceptance", x["execution_at"], x["execution_market"]) == executed
    at = x["sessions"][1].close_at
    changed_market = replace(
        x["execution_market"],
        quotes=tuple(
            replace(q, price=D(price), observed_at=at, available_at=at, kind="close")
            for q, price in zip(
                x["execution_market"].quotes, ("10.05", "20.05", "25.10"), strict=True
            )
        ),
        fx=FXBook((FXRate(at, at, D("1.30"), "synthetic_acceptance_revaluation", True),)),
    )
    valued = account.append("close-value", dict(kind="VALUE", at=at, market=changed_market))
    assert valued.state == executed.state  # Marking does not create a fill, fee or cash movement.
    assert valued.event_count == executed.event_count + 1
    cash = valued.state.balances()
    expected = Fraction(cash["CAD"]) + Fraction(cash["USD"]) * Fraction(13, 10)
    prices = {q.asset: Fraction(q.price) for q in changed_market.quotes}
    expected += sum(
        (
            p.quantity * prices[p.asset] * (Fraction(13, 10) if p.asset.currency == "USD" else 1)
            for p in valued.state.positions
        ),
        Fraction(0),
    )
    assert Fraction(valued.valuations[-1].nav_cad) == expected == Fraction(294910, 100)
    assert not valued.valuations[-1].violations
    # All connections are closed by the service; a fresh interpreter rebuilds the entire view.
    code = (
        "import json,sys; from pathlib import Path; "
        "from portfolio_research_desk.paper_store import PaperAccount; "
        "from portfolio_research_desk.domain import jsonable; "
        "print(json.dumps(jsonable(PaperAccount(Path(sys.argv[1])).load())))"
    )
    recovered = subprocess.run(
        [sys.executable, "-c", code, str(account.path)],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert json.loads(recovered.stdout) == jsonable(valued)
    fresh = PaperAccount(account.path)
    assert fresh.load() == valued
    report = write_paper_report(fresh, tmp_path / "reports", "acceptance")
    exported = json.loads((report / "account.json").read_text("utf-8"))
    assert exported["account"] == jsonable(valued)
    assert (report / "trades.csv").read_text().count("\n") == 4
    assert (report / "nav.csv").read_text().count("\n") == 3


@pytest.mark.parametrize(
    "old,new",
    [
        ('mode = "paper"', 'mode = "live"'),
        ('base_currency = "CAD"', 'base_currency = "USD"'),
        ("schema_version = 5", "schema_version = true"),
        ("top_k = 5", "top_k = false"),
        ('initial_cash = "3000.00"', 'initial_cash = "NaN"'),
        ("max_positions = 10", "max_positions = false"),
        ('fx_fee_bps = "20"', "fx_fee_bps = true"),
        ('max_sector_weight = "0.40"', 'max_sector_weight = "1.2"'),
        ('commission_bps = "5"', 'commission_bps = "NaN"'),
        ("top_k = 5", "top_k = 5\nunknown = 1"),
    ],
)
def test_config_rejects_invalid_and_unsupported_modes(tmp_path, old, new):
    path = tmp_path / "paper.toml"
    path.write_text(
        Path("configs/example_paper.toml").read_text().replace(old, new), encoding="utf-8"
    )
    with pytest.raises(ConfigError):
        load_paper_config(path)


def test_cli_manual_lifecycle_persistence_idempotence_and_immutable_export(tmp_path, capsys):
    db = tmp_path / "account.sqlite3"
    sample = tmp_path / "sample"
    x = example_inputs()
    assert main(["paper", "sample", "--output-dir", str(sample)]) == 0
    assert json.loads(capsys.readouterr().out)["data_kind"] == "synthetic"
    assert (
        main(["paper", "init", "--db", str(db), "--at", x["sessions"][0].open_at.isoformat()]) == 0
    )
    capsys.readouterr()
    assert (
        main(["paper", "propose", "--db", str(db), "--input", str(sample / "decision.json")]) == 0
    )
    proposed = json.loads(capsys.readouterr().out)
    record = proposed["plans"]["sample-plan"]
    assert record["status"] == "PENDING_REVIEW" and not proposed["state"]["positions"]
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "paper",
                "simulate",
                "--db",
                str(db),
                "--plan-id",
                "sample-plan",
                "--at",
                x["execution_at"].isoformat(),
                "--input",
                str(sample / "execution.json"),
            ]
        )
    assert exc.value.code == 2
    capsys.readouterr()
    assert (
        main(
            [
                "paper",
                "review",
                "--db",
                str(db),
                "--plan-id",
                "sample-plan",
                "--plan-hash",
                record["plan_hash"],
                "--approve",
                "--at",
                x["review_at"].isoformat(),
            ]
        )
        == 0
    )
    capsys.readouterr()
    command = [
        "paper",
        "simulate",
        "--db",
        str(db),
        "--plan-id",
        "sample-plan",
        "--at",
        x["execution_at"].isoformat(),
        "--input",
        str(sample / "execution.json"),
    ]
    assert main(command) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["plans"]["sample-plan"]["status"] == "SIMULATED"
    assert main(command) == 0
    assert json.loads(capsys.readouterr().out) == first
    assert main(["paper", "status", "--db", str(db)]) == 0
    assert json.loads(capsys.readouterr().out) == first
    assert (
        main(
            [
                "paper",
                "export",
                "--db",
                str(db),
                "--output-dir",
                str(tmp_path / "reports"),
                "--run-id",
                "manual",
            ]
        )
        == 0
    )
    report = Path(json.loads(capsys.readouterr().out)["report_directory"])
    marker = json.loads((report / "run.json").read_text())
    assert marker["event_count"] == 4
    for filename, digest in marker["files"].items():
        assert hashlib.sha256((report / filename).read_bytes()).hexdigest() == digest
    with pytest.raises(ReportError):
        write_paper_report(PaperAccount(db), report.parent, "manual")


def test_report_escapes_external_text_and_keeps_replay_inputs(tmp_path):
    x = example_inputs()
    a = PaperAccount.create(tmp_path / "account.sqlite3", x["sessions"][0].open_at)
    bundle = replace(x["bundle"], source="<script>alert('x')</script>")
    a.propose(bundle, x["market"], x["sessions"], x["decision_at"], "plan")
    directory = write_paper_report(a, tmp_path / "reports", "escaped")
    text = (directory / "report.html").read_text()
    assert "<script>" not in text and "&lt;script&gt;" in text
    events = json.loads((directory / "events.json").read_text())
    assert len(events) == 2 and events[-1]["event_id"] == "propose:plan"


def test_report_io_failure_leaves_no_completion_marker(tmp_path, monkeypatch):
    x = example_inputs()
    a = PaperAccount.create(tmp_path / "account.sqlite3", x["decision_at"])
    original = Path.write_text

    def fail(path, *args, **kwargs):
        if path.name == "report.html":
            raise OSError("disk full")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail)
    with pytest.raises(ReportError):
        write_paper_report(a, tmp_path / "reports", "broken")
    assert not (tmp_path / "reports" / "broken" / "run.json").exists()
    assert a.load().event_count == 1


@pytest.mark.parametrize(
    "contents",
    [
        "{}",
        "[]",
        '{"schema_version":4,"payload":null}',
        '{"schema_version":5,"payload":{"type":"Unknown","fields":{}}}',
    ],
)
def test_malformed_native_inputs_are_user_errors(tmp_path, contents):
    path = tmp_path / "input.json"
    path.write_text(contents)
    with pytest.raises(DataError):
        read_native(path)


@pytest.mark.parametrize(
    "command",
    [
        {},
        dict(kind="CASH"),
        dict(kind="VALUE", at="invalid", market=None),
        dict(kind="CASH", at=example_inputs()["decision_at"], currency="CAD", amount=D(1), fx=None),
        dict(kind="BOGUS", at=example_inputs()["decision_at"]),
    ],
)
def test_malformed_apply_command_exits_two_without_traceback(tmp_path, capsys, command):
    x = example_inputs()
    db = tmp_path / "account.sqlite3"
    a = PaperAccount.create(db, x["sessions"][0].open_at)
    path = tmp_path / "event.json"
    write_native(path, command)
    with pytest.raises(SystemExit) as exc:
        main(["paper", "apply", "--db", str(db), "--event-id", "bad", "--input", str(path)])
    assert exc.value.code == 2 and "Traceback" not in capsys.readouterr().err
    assert a.load().event_count == 1


def test_cli_rejected_execution_is_json_and_exit_two(tmp_path, capsys):
    x = example_inputs()
    db = tmp_path / "account.sqlite3"
    a = PaperAccount.create(db, x["sessions"][0].open_at)
    view = a.propose(x["bundle"], x["market"], x["sessions"], x["decision_at"], "plan")
    a.review("plan", x["review_at"], fingerprint(view.plans["plan"].plan), True)
    market = replace(
        x["execution_market"],
        quotes=tuple(replace(q, volume=0) for q in x["execution_market"].quotes),
    )
    path = tmp_path / "bad.json"
    write_native(path, market)
    assert (
        main(
            [
                "paper",
                "simulate",
                "--db",
                str(db),
                "--input",
                str(path),
                "--plan-id",
                "plan",
                "--at",
                x["execution_at"].isoformat(),
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["plans"]["plan"]["status"] == "REJECTED"


def test_phase4_predictions_adapter_ignores_labels_and_checks_fit_availability():
    x = example_inputs()
    at = x["decision_at"]
    rows = [
        dict(
            model="logistic",
            decision_at=at,
            available_at=s.available_at,
            fit_at=s.observation_start,
            asset=s.asset,
            score=float(s.score),
            target=0,
            forward_return=-0.9,
        )
        for s in x["bundle"].signals
    ]
    bundle = bundle_from_ml_predictions(
        rows, x["bundle"].universe, at, "logistic", data_kind="synthetic"
    )
    perturbed = [dict(row, target=1, forward_return=9999) for row in rows]
    assert (
        bundle_from_ml_predictions(
            perturbed, x["bundle"].universe, at, "logistic", data_kind="synthetic"
        )
        == bundle
    )
    with pytest.raises(DataError):
        bundle_from_ml_predictions(
            [dict(r, fit_at=at + timedelta(seconds=1)) for r in rows],
            x["bundle"].universe,
            at,
            "logistic",
            data_kind="synthetic",
        )


def test_native_string_cash_amount_is_clean_input_error(tmp_path, capsys):
    x = example_inputs()
    db = tmp_path / "account.sqlite3"
    account = PaperAccount.create(db, x["sessions"][0].open_at)
    path = tmp_path / "cash.json"
    write_native(
        path, dict(kind="CASH", at=x["decision_at"], currency="CAD", amount="10", fx=x["market"].fx)
    )
    with pytest.raises(SystemExit) as exc:
        main(["paper", "apply", "--db", str(db), "--input", str(path), "--event-id", "cash"])
    assert exc.value.code == 2 and "Traceback" not in capsys.readouterr().err
    assert account.load().event_count == 1


@pytest.mark.parametrize("kind", ["CASH", "CONVERT", "ACTION", "invalid_kind"])
def test_native_unhashable_fields_are_user_errors(tmp_path, capsys, kind):
    x = example_inputs()
    db = tmp_path / "account.sqlite3"
    account = PaperAccount.create(db, x["sessions"][0].open_at)
    if kind == "CASH":
        command = dict(kind=kind, at=x["decision_at"], currency={}, amount=D(10), fx=x["market"].fx)
    elif kind == "CONVERT":
        command = dict(kind=kind, at=x["decision_at"], source={}, amount=D(10), fx=x["market"].fx)
    elif kind == "ACTION":
        command = dict(
            kind=kind,
            at=x["decision_at"],
            asset={},
            action="DIVIDEND",
            amount=D(1),
            available_at=x["decision_at"],
            fx=x["market"].fx,
        )
    else:
        command = dict(kind={}, at=x["decision_at"])
    path = tmp_path / "invalid.json"
    write_native(path, command)
    with pytest.raises(SystemExit) as exc:
        main(["paper", "apply", "--db", str(db), "--input", str(path), "--event-id", "bad"])
    assert exc.value.code == 2 and "Traceback" not in capsys.readouterr().err
    assert account.load().event_count == 1


def test_native_numeric_plan_id_is_clean_input_error(tmp_path, capsys):
    x = example_inputs()
    db = tmp_path / "account.sqlite3"
    account = PaperAccount.create(db, x["sessions"][0].open_at)
    payload = {k: x[k] for k in ("bundle", "market", "sessions", "decision_at")}
    payload["plan_id"] = 123
    path = tmp_path / "decision.json"
    write_native(path, payload)
    with pytest.raises(SystemExit) as exc:
        main(["paper", "propose", "--db", str(db), "--input", str(path)])
    assert exc.value.code == 2 and "Traceback" not in capsys.readouterr().err
    assert account.load().event_count == 1
