# Phase 6 Acceptance Report — Product Integration & Delivery

Date: 2026-10-28. Version: **0.7.0 development version**.
Status: final local acceptance passed; safe private Git synchronization and exact-SHA
remote CI are authorized and being completed. User experience acceptance remains
reserved for the author; no formal v1.0.0 Release or public visibility is authorized.

## Scope, baseline and authorization

- Read AGENTS, the full original PROJECT_PLAN, DEVELOPMENT_LOG, README, Phase 5
  acceptance evidence, actual source/interfaces, environment and Git status first.
- Stable main / origin/main / branch HEAD before final synchronization:
  `2f6b18c6218b8ac9b529c5bc7f69ee875fc252c5` (accepted v0.6.0).
- New development branch: `codex/phase-6-product-integration`, created from stable main.
  Initial working tree was clean. Development was delivered uncommitted; the user
  subsequently authorized final acceptance, commit and private synchronization.
- Private repository remains `yufeizhang06/PortfolioResearchDesk`. Normal commits,
  safe main integration and normal push are now authorized after acceptance;
  force push, visibility change, formal Release and broker actions are excluded.
- Original PROJECT_PLAN SHA-256 remains
  `1f208c70b41aeaecfac45f1e38bcd2d3ff674f6eb1868352b45fd9eb40f752bb`.
- Baseline tests before development: **609 passed in 33.26s**. Existing tests and
  financial algorithms were retained; no failing regression was deleted.

## Delivered product behavior

| Requirement | Implementation and evidence |
|---|---|
| Clear complete entry point | `prd workspace init`, `doctor`, `workflow run/check`; one offline lifecycle across public services |
| Stocks/research/portfolio/backtest/Paper | Shared short synthetic universe and momentum; separate USD backtest; CAD plan/review/fill/mark/replay/export |
| Existing factor/ML access | Existing commands retained; optional full demo runs both, with distinct evidence scopes |
| Ordinary configuration and validation | Strict schema 6 workflow TOML and readable Paper JSON; editable packaged workspace; explicit costs/limits via existing Paper profile |
| Daily reviewed account use | `paper plan`, `summary`, `value`, `cash-flow`, `convert`, `validate-snapshot`; old native commands remain compatible |
| Reports and repeatability | Local HTML index, JSON/CSV audit exports, snapshots, provenance, last-written hash manifest and offline verifier |
| Installation | wheel/sdist plus packaged templates work outside source; clean exported-source installation also passes |
| Documentation | English README, USER_GUIDE, CODE_WALKTHROUGH, CONTRIBUTING, release readiness and updated architecture/changelog/log |
| Licenses/privacy | User-confirmed MIT, packaged third-party notices, installed license metadata inventory, ignored private/generated files |
| Independent review | Separate reviewer, 80 new tests and mixed CAD/USD independent numerical probe; no unresolved actionable P1/P2/P3 |

Streamlit was evaluated and **deferred**. CLI services and self-contained local HTML
cover the current workflow without a server, new dependency group or UI session
state around persistent accounts. This is a deliberate permitted scope choice;
no dashboard is represented as implemented. Base runtime remains standard-library
only. Version/metadata were updated with uv; no third-party lock version changed.

## Demonstration and independent financial checks

Final complete demo:
`work/phase6-final-desk/runs/acceptance/index.html`.
Its `workflow.json` verifies **63 artifacts**, including SQLite and all nested
reports. All inputs use invented assets, fixed explicit 2024 UTC dates and
`credible_real_market_oos=false`.

1. Workspace generated editable profiles, identity CSV and readable snapshots.
2. The workflow imported/saved/reloaded/exported the three-asset watchlist.
3. One-session **past-only** momentum generated research signals from the shared
   price fixture. Decision `2024-01-04T21:02:00+00:00`; execution at next declared
   open `2024-01-05T14:30:00+00:00`.
4. A CAD 3,000.00 account proposed Top-2 targets (20% each, 60% target cash).
   Pending plan and estimated orders/costs were saved before an explicitly
   **scripted synthetic demo** review. Daily manual commands require human review.
5. Two simulated fills; exact retry did not add a fill/event/fee. No risk violations.
6. At the closing mark, available CAD-per-USD changed from 1.35 to 1.30 and prices
   changed according to the fixture. A fresh account load recovered identical state.
7. JSON, trades/NAV CSV and HTML account reports were exported.
8. Optional factor diagnostics completed on their independent 96-observation
   known-answer fixture. All five ML models ran on a longer separate synthetic
   panel. The development-selected Logistic model generated a **pending-review,
   zero-fill** CAD preview; holdout results did not select it.

| Final account item | Actual value |
|---|---|
| CAD cash | 2,367.97 CAD |
| USD cash | 0.00 USD |
| SYN_A | 37 USD-denominated shares, close USD 12.00 |
| SYN_B | 1 USD-denominated share, close USD 20.00 |
| CAD holdings market value | 603.20 CAD |
| Opening NAV after fees/slippage | 2,997.0700 CAD |
| Closing NAV | **2,971.1700 CAD** |
| Cumulative CAD commission attribution | 0.6075 CAD |
| Cumulative FX cost / rounding attribution | 1.2830 CAD |
| Events / fills | 5 / 2 |
| Risk violations | none at recorded marks |
| Retry / recovery | identical |

Independent identity:
`2367.97 + (37 * 12.00 + 1 * 20.00) * 1.30 = 2971.17 CAD`.
Fees/FX costs are already reflected in cash and must not be deducted again.
Greedy sequential fee-aware risk sizing can put an early holding near its cap
and shrink later orders substantially as costs reduce NAV; target weights are not
promised execution weights. This example retains about 79.7% cash at the final
mark. The recorded reasons and target/order details remain visible; this phase
did not introduce a batch optimizer or hide the capital-utilization limitation.

A separate reviewer adapted the readable inputs to hold **both CAD and USD
assets**, used 18%/18% explicit targets, and independently recomputed NAV using
`fractions.Fraction`: **2 fills, 5 events, NAV 2929.9000 CAD**, retry/reload identical.
Missing/future FX, missing/future sector, negative/incorrect/over-limit target and
wrong review hash were rejected without state mutation.

The new manual CLI lifecycle test also verifies pending-review rejection, exact
approval, simulation retry, closing mark, same-time CAD deposit, stale-NAV flag,
revaluation, explicit CAD→USD conversion to USD 10.00 and independently expected
CAD 0.03 conversion cost. It reopens and compares the persisted account.

## Actual validation

Local platform: Windows, Python **3.12.14**, uv **0.13.6**.
Locked installation with `data`, `factors`, `ml` extras passed. Commands use the
existing populated offline cache; a clean machine still needs initial dependency
provisioning. Runtime tests use fixed inputs and pytest-socket prohibits sockets.

| Check | Actual result |
|---|---|
| Original baseline before changes | 609 passed, 33.26s |
| Original regressions after integration | 609 passed, 32.42s |
| New adapter/workflow/CLI tests | 80 passed, 12.43s |
| Independent reviewer new-test run | 80 passed, 12.50s |
| Final complete suite | **689 passed, 46.87s** |
| Ruff lint / format | passed, all 112 Python files formatted |
| uv lock check / locked sync | passed; only own-project version changes in lock |
| CLI/help / all seven config kinds / examples | passed locally; old commands retained |
| Full offline base + factor + ML workflow | complete; 63 artifact hashes verified |
| sdist + wheel | built offline with locked Hatchling |
| sdist rebuild + direct/rebuilt wheels | passed in two clean independent environments outside source |
| Installed base behavior | templates, diagnostic, readable snapshots, full base lifecycle/recovery/report check; missing extras fail before output |
| Installed optional behavior | factors, five-model ML, integrated full workflow and pending preview passed in both wheels |
| Clean exported-source install | no .git/work/.venv initially; locked offline sync, new spaced-path workspace and complete full workflow/check passed |
| HTML index QA | 10 local links, zero broken links, no remote resources/placeholders |
| Sensitive/generated file review | candidate scan found no credential patterns; archive excludes work/data/private/outputs/environments |
| License inventory | 57 locked third-party distributions; installed versions match; platform-specific nvidia-nccl-cu13 absent on Windows |
| Independent review | no unresolved actionable P1/P2/P3; final source snapshot reconciled |

Commands, from an ordinary checkout after dependency installation:

```bash
uv lock --check --offline
uv run --locked --offline pytest -p pytest_socket -q
uv run --locked --offline ruff check .
uv run --locked --offline ruff format --check .
uv run --locked --offline prd doctor --require data --require factors --require ml
uv run --locked --offline prd workspace init --directory work/my-desk
uv run --locked --offline prd workflow run --config work/my-desk/workflow.toml --run-id full --with-factors --with-ml
uv run --locked --offline prd workflow check --directory work/my-desk/runs/full
uv build --offline --no-build-isolation --out-dir dist/phase6
uv run --locked --offline python scripts/verify_distribution.py dist/phase6 --with-factors --with-ml
uv run --locked --offline python scripts/inspect_licenses.py
```

In this workstation `uv` is `work/bin/uv.exe`, with `UV_CACHE_DIR=work/uv-cache-phase3`
and `UV_PROJECT_ENVIRONMENT=work/phase4-venv`; these local paths are not project
requirements. Tests used `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, explicit
`-p pytest_socket`, an exclusive `--basetemp work/phase6-all-tests` and
`-p no:cacheprovider` to avoid unrelated old local temp permissions.

Evidence retained locally in ignored `work/`: `phase6-tests.log`,
`phase6-distribution.log`, `phase6-clean-install.log`, `phase6-doctor.json`,
`phase6-license-inventory.json`, `phase6-candidate-checks.json`, the final workspace
and independent review probes. The durable [independent review narrative](PHASE_6_CODE_REVIEW.md) and reviewed hashes
are included under `docs/` rather than requiring these local files for context.

Development failures were preserved, not masked: the first demo intentionally
exposed a fee/FX-gap risk rejection (no completion marker); the final fixture keeps
FX flat until after execution and changes it at valuation. Two new tests initially
used Windows' locale encoding when reading UTF-8 HTML; explicit UTF-8 fixed them.
Ruff preparation findings were corrected before acceptance. No test was removed.
The build tool warned about the cache located inside the checkout; archive member
inspection verified the allowlist excludes it. Isolated sync warned about an
inherited VIRTUAL_ENV; the explicit target environment and wheel origin assertions
proved installation stayed isolated, with no editable-source substitution.

## Final acceptance and private synchronization — 2026-10-28

The user explicitly approved this acceptance, commit, safe main integration,
normal private push and exact-SHA Ubuntu/Windows CI verification. No blocker was
found in preflight: all reviewed production/test/config/build files match the
independent snapshot. The three post-review MIT wording changes were recorded;
this closeout changes documentation only. No old test or financial algorithm is
modified. The independent report is preserved verbatim, with this later acceptance
clearly distinguished from a new independent review.

### Actual user-workflow checklist

All runs use explicitly synthetic data and test accounts. Evidence is retained in
`work/phase6-sync/commands.json`, `user-workflow-results.json` and per-command output;
17 actual CLI subprocesses exited with their expected codes. Successful status
alone was not sufficient: outputs, numerical values and saved/recovered states
were independently asserted by the acceptance driver.

| # | Requested behavior | Result | Actual evidence |
|---|---|---|---|
| 1 | Create/select universe | PASS | Identity CSV import/save via CLI: 3 explicit US/USD synthetic identities; selected watchlist used by research config |
| 2 | Screen stocks | PASS | Offline `universe build`: 3 evaluated, SYN_A/SYN_B included, SYN_C excluded with reason using momentum >= 0.01; screening.json retains values/reasons |
| 3 | Factor research/report | PASS | Full workflow FF3/FF4 HTML/JSON; 96 known-answer observations, FF4 Mom = 0.4999999999999997 |
| 4 | ML/walk-forward | PASS | All 5 declared models, 35 fold records, holdout metrics and predictions exported; frozen selected-model CAD preview stays pending with zero fills |
| 5 | Signals/target portfolio | PASS | Past-only momentum on shared execution fixture; target weights plus cash independently sum to 1; pending plan includes risk/cost/sizing reasons |
| 6 | Historical simulation/risk | PASS | Separate USD synthetic backtest: 10 fills, ending NAV USD 1256.28, max drawdown 0.04075558209875354; annualized metrics correctly null for short sample |
| 7 | 3,000 CAD account | PASS | Separate explicitly named test account initialized through `paper init` with CAD profile |
| 8 | Plan/review/simulate | PASS | Pending simulation exits 2; explicit exact-hash approval precedes next-open simulation; 2 fills |
| 9 | Cash/holdings/NAV | PASS | CAD 2367.97 / USD 0; SYN_A 37, SYN_B 1; closing CAD NAV 2971.1700; Fraction cash+holdings identity exact, no risk violations |
| 10 | Close/reopen/retry | PASS | Each CLI invocation is a new process; full status before/after duplicate execution identical; reopened summary equals saved post-mark summary, 5 events |
| 11 | Readable research/account exports | PASS | Factor/ML/USD HTML reports and index; manual account HTML, account/events JSON, trades/NAV CSV and completion marker all exist; integrated run's 63 artifact hashes verify |

Screening uses the Phase 2 provider-observation fixture; executable momentum,
USD history and the main CAD account share the stricter six-session execution
fixture. Factor and ML fixtures have their own explicitly documented ranges.
These are compatible accessible workflows, not a claim that an arbitrary selected
real universe automatically flows into a certified historical strategy. The
synthetic USD return and CAD NAV are separate demonstrations, not one strategy's
performance. The full workflow report is `work/phase6-sync/desk/runs/final/index.html`;
manual account export is `work/phase6-sync/manual-reports/final/report.html`.

| Additional capability | Result | Reason |
|---|---|---|
| Certified real-market historical PIT/OOS | NOT SUPPORTED | Membership/availability/action/calendar/source evidence gaps remain |
| Automatic arbitrary real-universe historical trading pipeline | NOT SUPPORTED | Real observations are not implicitly executable bars/signals |
| Streamlit Dashboard / live monitoring | NOT SUPPORTED | Deliberately deferred; CLI/local HTML available |
| Broker / real orders | NOT SUPPORTED | No broker integration; explicitly outside scope |

### Repeated local quality, license and distribution gates

- Full suite rerun: **689 passed in 43.20s** on Windows / Python 3.12.14.
- Ruff lint/format, locked offline sync and lock check passed. Original Phase 0–5
  tests remain; no test was removed or modified in this final acceptance.
- Offline wheel/sdist, sdist rebuild and both-wheel independent clean installation
  with base and factor/ML/full workflows are checked by verify_distribution.py;
  **PASS** on Python 3.12.14; actual log ends with the sdist/both-wheel/clean-install
  success marker (`work/phase6-sync/distribution.log`).
- LICENSE contains standard MIT terms, `Copyright (c) 2026 Yufei Zhang`, matching
  the configured Git author. pyproject uses SPDX MIT and packages LICENSE /
  THIRD_PARTY_NOTICES; README agrees. The user confirmed this choice.
- 57 third-party lock records were inventoried: no installed-version mismatch;
  Linux-only nvidia-nccl-cu13 is absent on Windows. Metadata inventory is not a
  blanket license clearance. Official MIT/yfinance/Nasdaq/French sources were
  rechecked; the existing separate software/data notices remain applicable.
- Private accounts, SQLite, market downloads, caches, local tools, raw logs and
  generated run outputs are excluded from candidate files. Intended review hashes
  and the compact synthetic numerical review result under docs/reviews are audit
  documentation, not a private account or downloaded dataset.

### Exact-SHA Git and Actions record

Local gates passed; commit/safe synchronization and actual remote CI are the
remaining authorized closeout actions. This paragraph will be replaced with
actual SHA/run evidence after execution, never inferred from CI configuration.
The stable Phase 5 CI run is baseline evidence only and is not reused for Phase 6.

## Known limitations and readiness

- This is a usable local CLI product, with manual available-input preparation for
  daily Paper use. No live quote monitor, automatic signal scheduler or GUI exists.
  The fixed demo is not an arbitrary-universe strategy builder.
- Real historical PIT, membership/delistings, identity changes, exchange calendars,
  historical sector/FX/source truth and complete corporate actions remain unverified.
  Caller-declared timestamps alone do not certify data. Real research is descriptive.
- ML purging/holdout tests establish synthetic software behavior, not real skill,
  research pre-registration or an untouched real holdout. Synthetic holdout is
  repeatedly used for regression tests. All results, including weak ones, remain.
- Cash/FX/price gaps may block a batch. Conservative greedy integer planning is
  feasible, order-dependent and may materially undershoot intended allocations.
- Only explicit simple supported splits/dividends are covered; adjusted-price
  misuse, complex/repeated/backdated actions are blocked. No tax ledger or complete
  total-return/corporate-action dataset is claimed.
- Recorded valuation freshness concerns subsequent account events, not a live
  market clock. Refresh using available quote/FX snapshots; exports are snapshots.
- Local SQLite/hash manifests are neither encrypted nor signed; trusted storage,
  backups and explicit migration design remain needed for future schema changes.
- MIT was confirmed by the user on 2026-10-28 for original project code and
  synthetic fixtures. Third-party data rights, native bundled
  components and any public redistribution need their separate review; no raw
  real market data or private holdings were added to source or distribution.
- macOS remains unverified. Exact-SHA Phase 6 Ubuntu/Windows evidence is recorded
  above when actually completed; passing local checks is not remote CI evidence.
  No automatic future scope, public publication or formal release follows.

Conclusion: the Phase 6 **local technical delivery gate** is met within the above
scope. The product can be installed, exercised offline and operated through
reviewed Paper commands without changing source. This authorized private sync does
not create a formal release; the author must next perform user experience acceptance.
