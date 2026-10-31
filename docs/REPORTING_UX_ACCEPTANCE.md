# CAD Paper reporting usability repair (2026-10-29)

Status: implemented and locally verified; awaiting the author's visual acceptance.
Local branch: `codex/paper-report-readability`. No commit, push, release or remote CI run.

## Review and scope

The previous `paper_reporting.py` embedded the entire account JSON in a `pre`
element. Repeated plans, audit inputs and unrounded Decimal strings obscured
portfolio results and produced an excessively long printout.

Keep the immutable JSON/CSV exports and accounting services. Add a dedicated,
standard-library HTML presentation module, with portfolio overview, allocation,
holdings, trading history, constraints and methodology. Add explicit generation,
valuation and input availability clocks. Format only displayed values; never
round or change audit inputs, ledger values or financial calculations.

Changes are limited to the Paper report writer, its presentation module, targeted
report regressions and documentation. Factor, ML and Backtesting presentation
remain deferred. No new dependency, server, broker or live data integration.

## Acceptance plan

- Re-export the existing first-use synthetic account without changing its ledger
  or original immutable report; compare raw account, events and CSVs.
- Check displayed amounts, quantities, weights, costs and FX against raw exports.
- Cover missing/stale valuation, same-time economic changes, cash-only/zero NAV,
  risk violations, pending/rejected plans, mixed provenance and escaped text.
- Run the existing offline suite and quality gates; build/install checks verify
  the new renderer is packaged and works outside the source tree.
- Print the actual HTML to A4 PDF, render and inspect every page, including a
  larger trading-history pagination check. Keep previews outside hashed bundles.

## Actual verification

Environment: Windows, Python 3.12.14, uv 0.13.6. Existing locked extras were
restored from the local cache. No dependency or lockfile change. Commands used
`work/bin/uv.exe` with `UV_CACHE_DIR=work/uv-cache-phase3`. For the explicit
`-p pytest_socket` test invocation, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` avoids
double-registering the same plugin; socket blocking stays enabled.

| Check | Actual result |
|---|---|
| Existing Paper/input/product workflow regressions | 105 passed |
| Final complete suite: `uv run --locked --offline pytest -p pytest_socket -q --basetemp work/report-final-tests` | **704 passed**, 48.94 seconds (689 existing + 15 report regressions) |
| `uv run --locked --offline ruff check .` | PASS |
| `uv run --locked --offline ruff format --check .` | PASS, 117 Python files |
| `uv lock --check --offline` | PASS, 58 locked packages |
| `uv build --offline --no-build-isolation --out-dir dist/report-ux` | sdist and wheel built |
| `uv run --locked --offline python scripts/verify_distribution.py dist/report-ux --uv <absolute work/bin/uv.exe> --with-factors --with-ml` | PASS: sdist rebuild, both wheels independently installed outside source; CLI, resources and full synthetic workflows |
| Original `prd workflow check --directory work/first-use-20261029/runs/first` | PASS, all 63 original files intact |
| Existing account export comparison | Exact account payload and plan hashes; events.json, trades.csv, nav.csv byte-identical; SQLite SHA-256 unchanged |
| New report integrity | All run.json file hashes verified; source hash matches final renderer |
| HTML browser check | No pre/script or external resources; download files exist; no document overflow at 1440px and 390px widths |
| A4 PDF from actual HTML | **2 pages**, 594.96 x 841.92 pt; both pages rendered through Poppler and visually inspected |
| Pagination stress fixture | 60 repeated presentation-only trade rows, 5 A4 pages, all 60 rows retained and table header repeated on 3 trade pages; all pages inspected |

Regression coverage includes amounts, local/CAD currencies, shares, weights,
holding P&L/percentages, executed fills, commissions/FX/slippage, NAV CSV and hash
manifest reconciliation. It covers same-time cash/conversion changes, a later
split, no valuation, cash-only/zero NAV, pending/rejected plans, risk breaches,
distinct generation/valuation/observation/availability timestamps, observed and
mixed inputs, HTML escaping, duplicate symbols on distinct exchanges, unchanged
output under altered Decimal context and invalid generation timestamps.

The initial runner setup exposed an auto-loaded pytest plugin duplication and a
missing ML extra. Both were resolved through environment configuration and locked
offline sync before the passing checks above. No failed test was removed.

## Review artifacts and reconciliation

Generated from the original first-use account, not a replacement account:

- HTML and exact downloads: `outputs/report-ux/cad-paper-account/report.html`.
- Browser-printed PDF: `outputs/report-ux/final-preview/cad-paper-account.pdf`.
- Screen and page images: `outputs/report-ux/final-preview/`.
- Exact preservation evidence: `outputs/report-ux/regression-check.json`.
- Browser evidence: `outputs/report-ux/final-preview/browser-check.json`.
- Build/install log: `work/report-ux-install.log`.

All previews remain in ignored local output directories. The PDF sits outside
the hashed report directory; adding it there would invalidate the manifest.
The original immutable run and its index are preserved. Future `paper export`
and `workflow run` commands use the new renderer automatically.

| Existing synthetic account | Display | Underlying value |
|---|---|---|
| NAV | CAD 2,971.17 | 2971.1700 |
| Cash translated to CAD | CAD 2,367.97 | 2367.9700 |
| Holdings value | CAD 603.20 | 577.2000 + 26.0000 |
| Account P&L | CAD -28.83 | 2971.1700 - 3000.00 net contributions |
| SYN_A | 37 shares, USD 12.00; CAD 577.20; 19.43%; P&L CAD -24.86 | Exact existing valuation row |
| SYN_B | 1 share, USD 20.00; CAD 26.00; 0.88%; P&L CAD -3.97 | Exact existing valuation row |
| Commission / FX cost / slippage | CAD 0.61 / 1.28 / 1.04 | 0.6075 / 1.2830 / 1.0395 |

The account was valued at **2024-01-05 21:02:00 UTC**. Its raw prices were observed
at 21:00 and available at 21:01; valuation FX was observed/available at 21:00.
The report's separate UTC generation timestamp is in October 2026. Matching the
latest ledger state does not mean current market quotes or certified historical PIT.

## Scope and remaining limits

- Only the existing report writer plus one presentation module change production
  behavior. No ledger, valuation, sizing, fee, FX, execution or strategy code changed.
- Account/plan schemas and CSV columns remain unchanged. `report_generated_at` is
  additive metadata outside the original account payload. Export provenance and
  HTML hashes appropriately differ from old reports; financial values do not.
- Company full names are absent from the current ledger. Synthetic asset labels
  or an explicit missing-name label accompany symbol/exchange/currency; no guessed
  company metadata or live lookups were introduced.
- PDF is a browser print of the self-contained HTML, not a new CLI PDF dependency.
  A4/portrait/100%/background graphics are verified in local Chrome 156. Browser
  font or print settings may change pagination. Longer accounts are not capped
  at two pages or silently truncated.
- Factor, ML and Backtesting layout migration is deferred; this is a static
  report dashboard, not a live portfolio application. Real PIT/OOS, tax and
  corporate-action limitations remain. No new remote-platform claim is made.

Stop here for the author's HTML/PDF experience acceptance.
