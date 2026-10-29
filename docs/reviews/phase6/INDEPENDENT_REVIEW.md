# Phase 6 independent code review

Review date: 2026-10-28. Reviewer: separate agent `phase6_review`.
Branch: `codex/phase-6-product-integration`.
Stable baseline: `2f6b18c6218b8ac9b529c5bc7f69ee875fc252c5`.
All Phase 6 changes remain uncommitted. The reviewer did not modify production
files/tests, commit, push, change main, contact a broker or use market downloads.

## Conclusion

**No unresolved actionable P1/P2/P3 findings in the reviewed integration code.**
This is a software review of Phase 6 integration and its use of existing contracts;
it is not certification of historical market PIT/OOS suitability, strategy profits,
data redistribution rights, a remote CI run or a formal release.

The code inspected is recorded in `reviewed-file-hashes.json`. Documentation and
installation evidence were still being finalized by the implementation agent;
final delivery must reconcile that evidence and any later source changes with
this snapshot. There was no known review finding hidden behind a passing test.

## Scope and reasoning

- Read current AGENTS, project plan, README, development/Phase 5 acceptance context,
  new readable JSON adapter, Paper services, command registration, orchestration,
  workspace/configuration/diagnostics, report hashing, packaging and CI changes.
- Traced readable inputs to `SignalBundle`, `Quote`, `FXBook`, `TargetPortfolio`
  and the existing `PaperAccount` / `propose_rebalance` / `simulate_plan` services.
  Financial calculation and execution rules are reused, rather than copied into
  the new CLI. Existing Phase 0–5 financial implementation was inspected at the
  relevant boundaries; this review does not claim an entirely new audit of every
  old module.
- Confirmed unknown fields, kinds, booleans, timestamps, duplicate assets/signals,
  adjusted prices and invalid weights fail closed; forward Paper input cannot
  declare verified PIT membership or enter historical CAD execution as real data.
- Confirmed plans remain pending exact-hash review, execution requires the planned
  next session open and unchanged account state, and duplicate retries use the
  ledger's idempotence rules. Cash/FX mutations flag previously recorded NAV stale,
  including mutations at the same timestamp as a prior valuation.
- Confirmed the unified demo always declares synthetic inputs and scripted demo
  review. Factor diagnostics do not drive orders; ML uses development-selected
  model records and produces a separate unexecuted pending-review CAD preview.
  USD historical results and CAD Paper NAV retain separate evidence scopes.
- Confirmed optional imports are preflighted, a run directory is exclusive,
  completion is written last, all nested artifacts are hashed, and verification
  rejects modified/missing/extra files and escaping paths. HTML index content is
  escaped and uses local artifact links.
- Inspected cross-platform pathlib use, explicit UTF-8 resource I/O, isolated
  installed-wheel checks, optional-extra separation and locked packaging metadata.
  Known Ruff fixes being handled by the author were not counted as new findings.

## Independent execution

Environment: Windows, Python 3.12.14; uv 0.13.6; locked existing environment and
offline cache. Tests used pytest-socket with socket access disabled.

```text
uv run --locked --offline pytest -p pytest_socket -q
  tests/test_paper_inputs.py tests/test_product_workflow.py tests/test_product_cli.py
  --basetemp work/phase6-review/targeted-r2 -p no:cacheprovider --tb=short
```

Actual result: **80 passed in 12.50s**. The first reviewer invocation used a
nonexistent parent for the explicit pytest temp directory (55 passed / 25 setup
errors); after creating only the reviewer directory the complete run above
passed. This was a reviewer command preparation issue, not a product defect.

Additional independent probe: `adversarial_probe.py`, results `probe-results.json`.
It changes the readable fixture to hold **both CAD and USD assets**, supplies
explicit 18%/18% targets and 64% target cash, then exercises plan, exact-hash
review, execution, repeated execution, a closing valuation and a fresh account
load. Actual result: **2 fills, 5 events, CAD NAV 2929.9000**.

The NAV was recomputed using `fractions.Fraction` from actual currency cash,
share quantities, raw close prices and CAD-per-USD 1.30, without calling the
production NAV function for the expected result. The result matched exactly;
retry and recovery snapshots were identical. Missing FX, future-only FX,
missing sector, future sector, negative target weight, target sum != 1,
over-limit target and a wrong review hash were each rejected without account
mutation.

## Remaining boundaries

- Local hashes detect accidental artifact changes, not a malicious rewrite of
  both artifacts and their manifest; they are not signatures or data truth checks.
- `doctor` discovers metadata/modules; execution preflight supplies actual import
  checks. It cannot prove all optional native libraries work without running them.
- `valuation_stale` concerns account mutations after the recorded valuation; quote
  freshness still comes from explicit timestamps and the account's age limits.
- Synthetic fixtures, user-declared forward observations and current membership
  remain distinct from verified historical data. The core restrictions on real
  PIT, survivorship, calendars and corporate actions remain in force.
- Source/build/install and Ubuntu/Windows CI claims in the final acceptance report
  require their own actual execution evidence; this review does not substitute
  for checks not run by the reviewer.

## Final focused reconciliation

After implementation freeze, the reviewer compared all 79 original reviewed file
hashes. Only `scripts/inspect_licenses.py` changed; rereading confirmed its inventory,
version checks and offline behavior remain the same, with the scope text formatted
across lines. Executing it returned **57 locked third-party package records and no
installed version mismatch**. It still makes no legal-clearance claim.

The reviewer read final English README, USER_GUIDE, CODE_WALKTHROUGH,
RELEASE_READINESS, CONTRIBUTING, THIRD_PARTY_NOTICES and the final installation
script. Ten documented command/help/configuration entry points actually exited 0
(details in `final-evidence-check.json`). Module names, schemas, workflow scope,
review requirements and manual example times agree with implementation. An imprecise
walkthrough sentence implying sector age configuration was identified and corrected
by the author to “select only available FX/sectors and enforce quote/FX age limits”;
the reviewer reread that exact correction. This leaves no unresolved actionable
P1/P2/P3 finding.

The reviewer inspected the author's actual evidence logs, without repeating a
full review or full test suite:

- `work/phase6-tests.log`: **689 passed in 46.87s**. This is author-run full-suite
  evidence, separate from the reviewer-run 80 tests above.
- `work/phase6-distribution.log`: actual terminal **PASS: sdist rebuild, both wheels,
  clean install and CLI/resources on 3.12.14**. The reviewed script runs both wheels
  from outside the source tree, base and optional factor/ML workflows, recovery and
  immutable artifact checks; no editable source install substitutes for the wheel.
- `work/phase6-clean-install.log`: the clean exported source path contains spaces;
  the final full workflow check returns `status=verified`, 63 artifacts and explicit
  synthetic / no-real-OOS metadata. This is local Windows evidence, not remote CI.

The new README correctly labels Phase 6 uncommitted/unpushed and Phase 5 CI as
baseline-only, defers Streamlit with a maintainability rationale, and preserves
real PIT/OOS, membership, calendar, action and redistribution limitations. The
MIT selection remains an uncommitted local proposal; publishing is not implied.

At the time of link checking, the only not-yet-created local target was the author's
in-progress `docs/PHASE_6_REPORT.md`; the author owns completing that acceptance
record and final links. No other local documentation link was missing. Final
updated code/config/build hashes and the six new guide hashes are recorded in
`reviewed-file-hashes-final.json`; the original snapshot is retained for comparison.
