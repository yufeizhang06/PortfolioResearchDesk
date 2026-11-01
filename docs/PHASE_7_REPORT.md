# Phase 7 — User Experience & GUI Integration

**Historical acceptance record: 2026-10-29 to 2026-10-31.** Windows GUI
startup/operation was manually confirmed. The repository is now Public; this
record separates the original reporting checks, first GUI checks and later CI.
Current capabilities: [GUI Guide](GUI_GUIDE.md) and [README](../README.md).
Exact-SHA CI and current release position: [Release Readiness](RELEASE_READINESS.md).

Functional closeout: commit `88f1104616c489c8896626d10d765100fefd5aea` safely
fast-forwarded to main and normally pushed; the repository was Private at that time.
Actual [CI 41175396204](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/41175396204)
passed Windows 742 tests and Ubuntu 741 tests / 1 Windows-specific skip, plus all
build/installation/GUI checks at that exact SHA. All 34 new CI log entries scanned
without secret findings. Full-history/data-rights/installation review and remaining
limits are in PUBLICATION_REVIEW; documentation-head CI is verified separately.

On 2026-10-29 the reporting work unified Factor/ML/Backtesting presentation and
produced the GUI design. Those local checks preceded the first GUI implementation
and the later functional commit/CI recorded above.

## Reporting baseline and preservation — 2026-10-29

The reporting baseline was Phase 6 closeout `30049898b042b85acb29b5d7cda1c48545fb3016`.
Work used `codex/paper-report-readability`, preserving the seven existing,
uncommitted CAD report files. Before refactoring, file copies, a binary diff and
SHA-256 inventory were saved under ignored `work/phase7-preservation/`. The backup
contains eight files: the seven accepted files plus this newly started phase record.
No reset/stash/branch switch was performed. Remote heads/CI are not inferred from
local tracking refs. The reporting-only checks preceded the later Phase 7 commit.

## Implementation plan

- Extract the approved typography, colors, metric cards, tables, formatters and
  print rules into a small shared presentation module; preserve CAD behavior.
- Add report-specific renderers for Factor, ML and Backtesting. Connect existing
  writers to them without changing financial calculations or raw payload schemas.
- Use metric cards, concise explanations, actual charts/tables and local audit
  downloads. Keep failed/unavailable results visible and distinguish synthetic
  software validation from observed ex-post research.
- Re-render saved first-use report outputs in new local review folders, compare
  all raw financial payloads and verify original immutable runs remain intact.
- Run regression/quality/build/install checks and inspect actual A4 PDFs page by
  page. Then deliver a detailed Streamlit page/service/workflow proposal for
  explicit approval before implementation.

## Delivered implementation

- `report_design.py`: approved CAD CSS/formatters/cards/tables extracted without
  changing the accepted CAD rendering; research sections and inline SVG helpers.
- `factor_report_html.py`: security and sample identity, alpha/beta/R², FF3/FF4
  comparison, rolling betas, coefficients/intervals/p values, diagnostics and VIF,
  quality counts, availability/retrieval metadata, warnings and downloads.
- `ml_report_html.py`: frozen development-selected model, separate development and
  holdout tables, all five models, fold boundaries/F1, confusion matrix, all 18
  stage/strategy outcomes, baselines and recorded cost sensitivity. Holdout NAV
  plots only its actual evaluation dates and explains the earlier cash-only ledger.
- `backtest_report_html.py`: NAV/return/drawdown/cash benchmark cards, NAV and
  drawdown charts, final holdings, all trades/fees/slippage, partial/cancelled
  orders, constraints, missing annualized statistics and methodology.
- Existing report writers now call those renderers; raw export schemas, existing
  chart downloads, immutable reservation and completion conventions remain intact.
  Factor generation time is captured once and shared by HTML and its manifest.
- `REPORT_DESIGN_STANDARD.md`: common visual, numeric, timing and print standard.
- `PHASE_7_GUI_PLAN.md`: six-page Streamlit plan, application service interfaces,
  workflows, capability boundaries, concurrency/idempotency and staged acceptance.
  No GUI code, Streamlit dependency, launcher or service has been implemented.

## Preservation and numerical evidence

Compared with the pre-Phase-7 SHA-256 inventory, only four existing source files
changed: `factor_reporting.py`, `ml_reporting.py`, `reporting.py` and the accepted
`paper_report_html.py` (shared-helper extraction). The new renderers/design module
are presentation files. Financial/model/portfolio/execution/ledger sources,
`paper_reporting.py`, `pyproject.toml` and `uv.lock` match the starting inventory.

The accepted CAD renderer was loaded from the preservation copy and compared with
the extracted version on the actual saved account, identical run ID and fixed
generation time: **HTML byte-for-byte identical**. Reading/rendering left the
account file unchanged:

`d498030d108d4b7d0c737b823928b86d384d90446294a09e969503390438cbce` (SHA-256).

The first-use source workflow at `work/first-use-20261029/runs/first` still passes
`verify_workflow_report`: all **63 files** verified. Original HTML, snapshots,
ledgers, CAD records and hashes were not rewritten.

For visual acceptance, existing outputs were read directly, not recomputed or
represented by Mock UI. Factor/ML/Backtesting copied **15 / 17 / 8** source files
respectively; all 40 copies match source bytes and SHA-256. Original `run.json` is
copied as `source-run.json`. A new `run.json` explicitly identifies a
`presentation-preview`, records origin and copy hashes, and hashes the replacement
HTML. It does not pretend that the old completion manifest certifies a new HTML.
PDFs/screenshots are outside the report directories. Reconciliation evidence is
`outputs/phase7-review/delivery/reconciliation.json`.

| Actual saved output | Raw result → displayed result |
|---|---|
| Factor FF4 alpha | approximately 0.0002 per observation → **0.0200% per day** |
| Factor market beta / R² / sample | approximately 0.8 / 0.999150061 / 96 → **0.800 / 99.92% / 96** |
| ML frozen choice | **Logistic regression**, despite Lasso's higher holdout F1 |
| ML holdout accuracy / F1 / AUC | 0.852941176… / 0.869565217… / 0.875388199… → **85.29% / 0.870 / 0.875** |
| ML scored coverage | **102 of 120**, 18 excluded; exclusions are not scored as zeros |
| USD backtest ending NAV / return | 1256.28 / 0.25628 → **USD 1,256.28 / 25.63%** |
| USD max drawdown / commission / slippage | 0.040755582… / 2.45 / 3.27 → **4.08% / USD 2.45 / USD 3.27** |
| Unchanged CAD account | **CAD 2,971.17 NAV; CAD 2,367.97 cash; CAD -28.83 account P&L** |

Visible coefficients, model comparisons, every stage/strategy portfolio row,
selected-model cost scenarios, holdings and fills were reconciled against these
actual saved payloads as well as freshly produced offline test bundles.
No market-performance claim follows from these numbers.

## Automated and visual verification

Windows / Python 3.12.14 / uv 0.13.6, existing locked environment. Commands use
`UV_CACHE_DIR=work/uv-cache-phase3`; pytest uses `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`
and explicitly loads `pytest_socket` to avoid duplicate host plugin registration.

| Check | Command / evidence | Result |
|---|---|---|
| Full regression | `uv run --locked --offline pytest -p pytest_socket -q --basetemp work/phase7-full-tests` | **721 passed** (56.15s), including the 17 new reporting cases |
| Final display adjustments | same pytest invocation for `tests/test_unified_reporting.py tests/test_paper_reporting.py`, then the 17 unified cases after adding header security identity | **32 passed**, then **17 passed** |
| Lint / formatting | `uv run --locked --offline ruff check src tests scripts`; `ruff format --check src tests scripts` | Passed; 97 files formatted |
| Lock consistency | `uv lock --check --offline` | Passed; 58 packages, no lock changes |
| Build / independent installs | `uv build --offline --no-build-isolation --out-dir dist/phase7-delivery`; `scripts/verify_distribution.py dist/phase7-delivery --uv work/bin/uv.exe --with-factors --with-ml` | Passed on the final report sources: sdist rebuild, both wheels, clean installs and CLI/resources; `work/phase7-delivery-install.log` |
| Saved-run integrity | `verify_workflow_report` and copy/hash/visible-cell reconciliation | 63 original files and 40 preview copies verified |
| Browser | Chrome/Playwright, 1440px desktop and 390px narrow viewport; network requests blocked | No JS errors, no body overflow, no `<pre>`, all audit links exist |
| Print | Actual HTML → browser A4 PDF → Poppler page PNGs; PDF text/size checks | Factor **3**, ML **5**, Backtesting **3** A4 pages |

The 17 new cases cover exact audit payload preservation when rendering is replaced,
rendered numeric reconciliation, undefined AUC, unchanged frozen selection,
failed analysis/windows, monthly alpha labeling, empty holdings/fills, escaping,
context-independent rounding, UTC offset conversion, chart gaps and single points.
The 15 accepted CAD tests remain part of the full suite. No failed tests were removed.

Visual review examined every delivered page for cropped content, broken rows,
chart labels, section starts, table widths and footer page numbers. Adjustments
removed a short trailing backtest page, gave ML portfolio comparisons and charts
explicit pages, improved narrow-screen axis text and kept the security identity
on the Factor first page. No GUI Mock or source-only assertion substitutes for
the rendered evidence. PDFs use a small QA footer with page counts; ordinary
browser printing can disable its default URL/date headers.

## Review artifacts

The original generated review bundles remained in ignored local output paths:

| Local artifact | Recorded visual check |
|---|---|
| `outputs/phase7-review/delivery/html/` | Paper/Factor/ML/Backtesting HTML and the local review index |
| `outputs/phase7-review/delivery/pdf/factor.pdf` | A4, 3 pages |
| `outputs/phase7-review/delivery/pdf/ml.pdf` | A4, 5 pages |
| `outputs/phase7-review/delivery/pdf/backtest.pdf` | A4, 3 pages |

These generated assets and the original local rendering/printing helpers are not
shipped. Reproduce current report output using the packaged synthetic workflow in
the [README](../README.md#complete-synthetic-demo-without-an-api-key), then open or
print the generated HTML. Browser printing is a QA/export option, not a production
Python dependency. The [GUI design](PHASE_7_GUI_PLAN.md) remains available in source.

## Reporting-check limitations — 2026-10-29

These original checks were local Windows evidence. Later Phase 7 Ubuntu/Windows
CI is recorded at the top of this report and in [Release Readiness](RELEASE_READINESS.md).
Original Phase 6 CI is not reused as evidence for a different revision.

Factor is ex-post; synthetic ML/backtesting do not certify real-market PIT/OOS or
profitability. Source availability is recorded metadata, not independent historic
publication proof. The current USD engine supplies no annualized return/volatility/
Sharpe estimate, and its baseline is cash. Reports display those limits clearly.
PDF page counts describe these fixtures; longer histories paginate naturally.

The subsequent implementation below added the proposed service layer and the
first GUI journey; broader planned forms remain outside that first scope.

## First GUI implementation — 2026-10-29

The first runnable Home → Stock Explorer → Research journey followed the existing
GUI design and shared report language. Development used `codex/phase-7-gui` from
`30049898b042b85acb29b5d7cda1c48545fb3016`; local implementation checks preceded
the functional commit and exact-SHA CI listed at the top.

### Preservation and implemented scope

Before GUI edits, all **18** dirty/untracked report files were copied under ignored
`work/phase7-gui-preservation`, with binary diff, Git status and SHA-256 manifest.
Each copy matched its source. The **11** report production/test files in that
inventory still match those hashes after GUI development; documentation updates
are additive/current-state changes. Original first-use workflow still verifies
all **63** files. No existing test or report engine was rewritten for the GUI.

- `app_contracts.py` and `app_services.py`: UI-independent requests, capabilities,
  confined workspace paths, immutable task results and integrity checks.
- `gui/`: Streamlit shell, six navigation entries, Home, watchlist/data forms,
  Factor input checks and results, current GUI report list and read-only Paper.
- Home supports environment inspection, empty state, recent tasks and a separate
  existing synthetic 3,000 CAD demo. Historical CAD NAV/valuation clocks remain explicit.
- Watchlists support code paste, per-row editable identity, CSV import/preview,
  duplicate/error visibility, immutable versions, reload and CSV download.
  Data uses packaged SYN_FACTOR, native local files or explicit opt-in yfinance.
  Offline requests cannot silently fetch or substitute synthetic prices.
- Factor uses the exact exported price/metadata reference from a verified data
  task. Typed config is revalidated by the existing engine. Both FF3/FF4 share the
  common sample; daily/monthly units, failed windows, warnings and full audit survive.
- Form changes do not fit/save automatically. Input checks are bound to current
  parameters; changed inputs must be checked again. Same command+input reuses an
  existing verified result; explicit new experiments use new IDs. Incomplete or
  corrupt directories remain visible and cannot masquerade as completed results.
- Windows setup/start launchers and installed `prd-gui` listen only on 127.0.0.1.
  No user JSON/TOML/CLI operation is needed for the first research journey.

The new GUI does not change model fitting, returns, execution simulation, risk
limits, FX, valuation or ledger code. Paper queries call the existing account
summary; no user-account propose/review/execute/write API exists in this iteration.
The fixed demo retains its pre-existing synthetic-only scripted review in a new
account. Real-pool backtesting, real PIT/OOS and brokers are capability-blocked.

### Actual automated verification

Windows / Python 3.12.14 / uv 0.13.6. `gui` fixes Streamlit **1.66.1**, compatible
with Python 3.12; resolved and installed alongside the scientific extras. Official
references: [PyPI metadata](https://pypi.org/project/streamlit/1.66.1/),
[navigation](https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation).
Installed license metadata reports Apache-2.0 and no installed/lock version mismatches.
The lock contains **76** packages. The base CLI still has no mandatory runtime dependency.

Commands use `UV_CACHE_DIR=work/uv-cache-phase3` and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
AppTest's Windows asyncio loop needs a socketpair; only `tests/test_gui.py` uses
pytest_socket loopback allow-hosts (127.0.0.1/::1), not external network. The host's
restricted runner blocked that local socketpair, so the GUI test runner/server
used approved execution outside that restriction. All other tests disable sockets.

| Check | Actual result |
|---|---|
| Pre-GUI baseline full pytest | **721 passed**, 61.67s |
| New service + AppTest tests | **21 passed**, 7.81s |
| Full suite including all old tests | **742 passed**, 59.32s; final code rerun **742 passed**, 57.99s |
| Subsequent display/iframe changes | GUI AppTest **3 passed**; final responsive font is presentation CSS only |
| Ruff lint/format | PASS; 135 Python files formatted |
| `uv lock --check --offline` | PASS; 76 packages |
| Build and independent installed checks | sdist rebuild, direct/rebuilt wheels, clean CLI/resources, full factors/ML workflows and installed GUI AppTest PASS; logs `work/phase7-gui-install.log`, `work/phase7-gui-final-install.log`. Final presentation sources rebuilt in `dist/phase7-gui-handoff`; both wheels' base CLI + optional GUI checks PASS (`work/phase7-gui-handoff-install.log`). |
| Reporting preservation / original workflow | 11 report source/test hashes unchanged; original 63 files verified |

New tests cover identities and duplicates, malformed rows, path escape rejection,
snapshot restart, exact engine-result equality, repeated/conflicting commands,
real/synthetic mismatch, offline cache miss without fallback, monthly/rolling
constraints, failed samples, incomplete/corrupt tasks, capability rejection,
read-only account bytes, workspace switching and GUI input-check invalidation.
The initial integration failure (existing workflow returns a result dict rather
than a Path) was fixed in the new adapter, without changing that backend API.

### Actual local interface verification

The real Streamlit service was driven in the in-app Chromium browser, not a Mock:

- Home: created an empty workspace, viewed empty states/environment, ran the
  isolated synthetic CAD demo and opened its read-only account. Recorded values
  match the existing backend: CAD **2,971.17 NAV**, **2,367.97 cash**, **603.20
  holdings**; valuation **2024-01-05 21:02 UTC**. Paper→Home keeps the selected account.
- Explorer: confirmed US/XNAS/SYN_FACTOR/USD, saved/reloaded the list, acquired
  **97** accepted observations, **0** quarantined; viewed actual price/source/time
  information and handed the exact snapshot to Research.
- Research: input check found **96** common samples; real FF3/FF4 run completed.
  Displayed FF4 alpha **0.0200% per day**, beta **0.800**, R² **99.92%** agree with
  saved output. Overview, formatted Details and Methodology tabs were inspected.
  The approved chart CSS was reused after finding missing legend styling.
- Download: clicked the actual report ZIP button. The downloaded
  `Downloads/prd-cab8f640.zip` has **16 files**, all byte-identical to its saved
  report directory. The delivery wait was unusually long; file/content verification
  confirms the completed download, but no normal-download latency claim is made.
- Restart: stopped/restarted the process, reopened the same workspace and recovered
  the same price and factor references without recomputation or config editing.
- Responsive: desktop and **390px** browser inspection; Home uses two cards per row,
  document width **390px** (no body overflow). Sidebar collapses on narrow screens;
  tables retain local scrolling. Metric font was reduced within the same design tokens
  to make narrow monetary cards easier to read. Browser viewport restored after QA.

Screenshots are local/ignored in `outputs/phase7-gui-review/`, including
`home-desktop.jpg`, `home-mobile.jpg`, `explorer-desktop.jpg`, `research-desktop.jpg`.
Final narrow-card font was visually rechecked at **21px** with all CAD amounts visible;
viewport was restored. Original self-contained
report/PDF acceptance remains above; the GUI's read-only preview has no active
relative audit links, while the downloaded HTML bundle retains working local links
and its original A4 print styles. No production browser/PDF dependency was added.

### First-GUI limits

Only the first journey is complete. Screening UI, ML/backtest forms, Paper writes,
background/cancel jobs, automatic refresh and a general index of pre-existing CLI
reports are deferred. Real-data live requests were not made in this acceptance;
native-real/monthly contracts rely on existing backend validation and tests.
Local-only app has no multi-user/authentication or cloud deployment scope.
The local checks above and the later dual-platform CI are separate evidence.
Current startup instructions are in [GUI_GUIDE](GUI_GUIDE.md); use `Start GUI.cmd`
and open the loopback URL only while the local application is running.
