# PortfolioResearchDesk

## Project Overview

PortfolioResearchDesk is a local-first Python platform for equity research,
stock screening, strategy simulation, and portfolio analysis. Its long-term goal
is a reproducible workflow from universe selection to research signals,
portfolio construction, backtesting, and paper portfolio review.

**Development version: 0.4.0.** Phases 0–3 have passed user acceptance.
Phase 3 is accepted for ex-post descriptive factor research after independent
verification of fixes R1–R5. This is not certification of a PIT trading strategy
or OOS performance. Machine learning and persistent paper accounts remain planned.
The system does not connect to brokers or execute real orders.

## Key Features

- **Custom Watchlists:** import/export identity CSVs; save, load, update, and
  deduplicate lists using market, exchange, symbol, and currency.
- **Market Universe:** retrieve the official Nasdaq Trader current listed-security
  directory with source, snapshot time, membership labels, and coverage warnings.
- **Rule-Based Screening:** combine minimum history, liquidity, price momentum,
  and historical volatility rules on custom or market universes; retain each
  inclusion or exclusion reason.
- **Data Adapters:** retrieve US/USD daily observations through yfinance or load
  native CSV/Parquet files with explicit provenance and price conventions.
- **Cache and Quality:** immutable snapshots, SHA-256 checks, SQLite lookup,
  expiry policies, offline replay, bounded retries, and explicit failures.
- **Synthetic Backtesting:** past-only momentum, Top-K equal-weight targets,
  integer shares, next-session execution, fees, slippage, cash, and NAV accounting.
- **Auditable Outputs:** configuration, data/code fingerprints, quality and
  screening reports; JSON/CSV research exports and JSON/CSV/HTML backtest reports.
- **Factor Diagnostics:** US French daily/monthly factors, same-sample FF3/Carhart
  FF4 OLS, classical or HC3 inference, residual/collinearity diagnostics, trailing
  exposures, and JSON/CSV/HTML/SVG/PNG reports.

## Current Development Status

| Area | Status in v0.4.0 |
|---|---|
| Installable package, CLI, strict TOML configuration | Implemented and locally tested |
| Custom / Market / Screening and combined modes | Implemented and locally tested |
| Real-data retrieval, local adapters, cache, quality | Implemented; live retrieval and cached replay verified locally |
| Execution and portfolio accounting | Validated on fixed synthetic USD fixtures |
| Backtesting with real market data | Not enabled; data and execution assumptions need further validation |
| Historical membership and delisted-security coverage | Not available; survivorship bias remains unresolved |
| FF3/FF4, OLS, rolling beta | Accepted for descriptive attribution; R1–R5 independently verified |
| ML and purged walk-forward OOS evaluation | Planned for Phase 4 |
| CAD/FX and persistent paper portfolios | Planned for Phase 5 |
| Dashboard and V1.0 release | Planned for Phase 6 |

Phase 3 is accepted locally; its approved changes are being committed and merged
from the separate development branch into `main`. The updated Phase 3 CI is
pending remote execution. Check the repository's Actions page for actual remote
results; local success alone does not establish them.
The [initial verified CI run](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40544579916)
passed on both Ubuntu and Windows after the fresh-checkout test configuration fix.

## Architecture Overview

The project uses a modular monolith. CLI commands call reusable services;
screening, portfolio, and execution logic do not depend on a specific provider
or user interface.

```mermaid
flowchart TD
    C[Custom Watchlist] --> U[Universe Snapshot]
    M[Nasdaq Current Directory] --> U
    U --> R[Research Workflow]
    A[yfinance or Native CSV / Parquet] --> H[History / Observation]
    H --> Q[Cache and Quality Checks]
    H --> FR[Period Returns and Common Sample]
    FF[French FF3 and Mom Snapshot] --> FR
    FR --> FA[OLS and Trailing Factor Diagnostics]
    FA --> FO[Descriptive Factor Audit Reports]
    Q --> R
    R --> S[Optional Rule Screening]
    S --> O[Universe and Audit Reports]
    F[Synthetic Fixture and Session Manifest] --> B[Momentum and Target Portfolio]
    B --> E[Next-Session Execution and Accounting]
    E --> P[Backtest Reports]
```

Research observations preserve provider precision, unknown event times, and
data availability. They are distinct from executable backtest bars. Real
observations are not routed into the synthetic execution pipeline.

Historical inputs must satisfy `available_at <= decision_at < execution_at`.
Unknown timing or coverage cannot be treated as verified point-in-time (PIT) or
out-of-sample (OOS) evidence. See [Architecture](docs/ARCHITECTURE.md) and
[Data Policy](docs/DATA_POLICY.md).

## Installation

Requirements: **Python 3.12.x** and **uv 0.13.6**. Clone this repository and run
from its root. Initial installation needs network access; offline examples
do not need an API key or market connection.

Windows PowerShell:

```powershell
py -3.12 -m pip install uv==0.13.6
py -3.12 -m uv sync --locked --extra data --extra factors --python 3.12
```

macOS / Linux:

```bash
python3.12 -m pip install uv==0.13.6
python3.12 -m uv sync --locked --extra data --extra factors --python 3.12
```

Commands below assume `uv` is on PATH. Otherwise use `py -3.12 -m uv` on Windows
or `python3.12 -m uv` on macOS/Linux. No virtual environment activation is needed.
See the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/)
if your system restricts global tool installation.

The `data` extra installs yfinance and PyArrow, with dependencies fixed in
`uv.lock`. The base package supports synthetic examples and native CSV research
using the standard library. Full adapter tests, live data, and Parquet need the
extra. The `factors` extra installs locked NumPy, SciPy, statsmodels and matplotlib.
With dependencies cached, use `uv sync --locked --extra data --extra factors --offline`.

## Quick Start

Run offline synthetic factor research (96 known-answer observations):

```bash
uv run --locked --offline prd config validate --kind factors --config configs/example_factors.toml
uv run --locked --offline prd research run --config configs/example_factors.toml
```

Open `report.html` in the returned `report_directory`. It includes common-sample
FF3/FF4 estimates, standard errors, t/p values, confidence intervals, R², adjusted
R², AIC/BIC, diagnostics, a beta heatmap and trailing exposure charts. JSON contains
input snapshots, exclusions and every rolling-window result. Alpha is a decimal
return per observation period; no automatic annualized alpha is claimed.

For live **descriptive** AAPL research, review dates and sources, then run:

```bash
uv run --locked --offline prd research run --config configs/example_factors_real.toml
uv run --locked --offline prd research run --config configs/example_factors_real.toml --offline
```

The first command can access French and Yahoo; the second requires their valid
caches. French percent returns are divided by 100 once. Response = stock return
minus same-period RF; `Mkt-RF` is already market excess return. FF4 adds French Mom,
not an individual stock's momentum score. Both models use identical complete cases.
No factors or rolling coefficients enter backtest decisions. See
[Factor methodology and configuration](docs/FACTOR_RESEARCH.md).

Run the packaged, explicitly **synthetic** research workflow:

```bash
uv run --locked --offline prd --help
uv run --locked --offline prd demo
uv run --locked --offline prd universe build
uv run --locked --offline prd data fetch --config configs/example_research_offline.toml
```

Run the synthetic backtest and its hand-checkable accounting scenario:

```bash
uv run --locked --offline prd backtest run --config configs/example_backtest.toml
uv run --locked --offline prd backtest run --config configs/example_handcheck.toml
```

These results validate timing and accounting, not market performance. Backtests
write to `outputs/runs/<run_id>/`; research writes to
`outputs/research/<run_id>/`. Existing runs are never overwritten. A final
`run.json` marks a completed report bundle; inspect its status and warnings.

For real-data descriptive research, review and edit the example date range and
asset list first. The examples use AAPL/MSFT, USD, and
`[2026-10-01, 2026-10-27)`, with an exclusive end date:

```bash
uv run --locked --offline prd data fetch --config configs/example_real_research.toml
uv run --locked --offline prd universe build --config configs/example_market_research.toml
uv run --locked --offline prd universe build --config configs/example_market_research.toml --offline
```

The first two commands may access market sources. **`uv --offline` only prevents
dependency downloads.** The final application-level `--offline` prohibits remote
data requests and requires valid existing cache entries. `--allow-stale` permits
expired entries explicitly and records that choice; `--refresh` requests a new
snapshot. Source failures never trigger a synthetic fallback.

Research configuration uses `schema_version=2`:

| Setting | Behavior |
|---|---|
| `universe.mode="custom"` | Explicit identity tables or a saved watchlist |
| `universe.mode="market"` | Current Nasdaq directory, optional custom additions and include/exclude filters |
| `universe.mode="screening"` | Rules applied to an explicit custom base |
| `screening.enabled=true` | Rules combined with AND; supported for custom and market modes |
| `data.expected_kind` | Required real/synthetic distinction; mixed identities rejected |
| `data.max_assets` | Configurable request budget; exceeding it fails without silent truncation |
| `research.require_point_in_time=true` | Blocks unverified historical membership |

Paths inside research TOML files resolve relative to that file. The
`--config` path itself resolves from the calling directory. Validate explicitly:

```bash
uv run --locked --offline prd config validate --config configs/example_offline.toml
uv run --locked --offline prd config validate --kind backtest --config configs/example_backtest.toml
uv run --locked --offline prd config validate --kind research --config configs/example_real_research.toml
```

Watchlist CSVs require the header `market,exchange,symbol,currency`. After
creating your local input file:

```bash
uv run --locked --offline prd universe watchlist import --input data/my_watchlist.csv --output data/watchlist.json --kind real
uv run --locked --offline prd universe watchlist update --input data/watchlist.json --output data/watchlist.json --add US:XNAS:NVDA:USD --remove AAPL
uv run --locked --offline prd universe watchlist export --input data/watchlist.json --output data/export.csv
```

Use `watchlist="../data/watchlist.json"` in place of `assets` in a configuration
under `configs/`. For native file inspection and conversion, use
`prd data check --help` and `prd data convert --help`. CSV requires its matching
`.metadata.json`; Parquet embeds metadata. Arbitrary vendor CSVs need an explicit
mapping to the native contract first.

CLI results are JSON on stdout; diagnostics use stderr. Expected input errors
exit 2. Multi-asset requests may finish with `status="partial"` and exit 0 when
usable data remains; review failures and quarantined observations.

## Testing

Install the locked environment with the `data` and `factors` extras, then run:

```bash
uv lock --check --offline
uv run --locked --offline pytest -q
uv run --locked --offline ruff check .
uv run --locked --offline ruff format --check .
uv run --locked --offline prd config validate --kind research --config configs/example_research_offline.toml
uv run --locked --offline prd config validate --kind factors --config configs/example_factors.toml
uv run --locked --offline prd research run
uv build --offline --no-build-isolation --out-dir dist/phase3
uv run --locked --offline python scripts/verify_distribution.py dist/phase3 --with-factors
```

Phase 2 acceptance recorded **208 passing tests**, including Phase 0–1
regressions. The verified Phase 2 Ubuntu and Windows CI jobs each also passed all 208
tests, lint, CLI, build, and isolated installation checks. Tests use fixed
fixtures and injected transports; pytest-socket
blocks sockets in the test process. Live source checks are separate manual
integration checks, not a dependency of CI.
Pytest uses the platform's default temporary directory; tests do not require a
pre-existing local work directory.

The distribution check rebuilds a wheel from the sdist, installs both wheels in
a clean environment, and runs Phase 0–2 commands outside the source tree. CI
targets Python 3.12 on Ubuntu and Windows. Checkout and dependency installation
need network access; test and example execution is offline. Remote status is
established only by actual GitHub Actions runs.

Phase 3 local results and limitations are recorded in
[Phase 3 acceptance](docs/PHASE_3_REPORT.md); Phase 3 remote CI is unverified.
The initial Phase 3 suite passed 270 tests; R1–R4 added 28 regression cases.
The R5 fix adds 32 time-alignment cases, bringing the suite to **330 tests**;
all original tests are retained.

## Project Structure

```text
src/portfolio_research_desk/
    cli.py, data_cli.py                  CLI boundaries
    config.py, backtest_config.py,
    research_config.py                  Strict configuration schemas
    domain.py, data_contracts.py         Shared types and quality validation
    data_adapters.py, data_cache.py      External/local data and snapshots
    universe.py, screening.py           Universe management and rules
    market_data.py, signals.py,
    portfolio.py, execution.py,
    backtest.py                         Synthetic simulation pipeline
    research_workflow.py, reporting.py   Orchestration and audit output
    factor_data.py, factor_returns.py    French snapshots, returns and alignment
    factor_analysis.py                  OLS, diagnostics and trailing windows
    factor_config.py, factor_cli.py,
    factor_workflow.py,
    factor_reporting.py                 Factor service, CLI and audit reports
    resources/                          Fixed synthetic data and defaults
configs/                                Editable Phase 0–2 TOML examples
tests/                                  Offline unit/integration/regression tests
scripts/                                Distribution verification
docs/                                   Plan, architecture, policy, acceptance logs
.github/workflows/                      CI
```

Local `data/`, `outputs/`, `work/`, virtual environments, credentials, and build
artifacts are excluded from Git. Downloaded real market data is not distributed.

## Data Sources & Limitations

- **Yahoo via yfinance:** a third-party research interface, not an exchange's
  official market data API. Availability, history revisions, delisted securities,
  and redistribution rights are not guaranteed. Review the
  [yfinance documentation](https://ranaroussi.github.io/yfinance/) and applicable
  Yahoo terms before use; raw downloads remain local.
- **Nasdaq Trader:** the [official current directory](https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt)
  is a current listed-security snapshot, not Nasdaq-100, S&P 500, or historical
  membership. ETF/test/NextShares records are excluded, but some warrants and
  other non-common-stock securities remain.
- **Survivorship and identity history:** historical index members, complete
  delisted coverage, mergers, and renaming maps are unavailable. Survivorship
  bias is unresolved. Current membership cannot be presented as historical PIT.
- **Time availability:** Yahoo daily `event_time` is unknown.
  `observation_end` is an explicitly labelled local-date upper bound;
  `available_at` is actual retrieval time. Historical publication times are not
  invented. Known events must match the supported exchange's local session date.
  Contradictory time labels are quarantined and factor research rejects them
  before regression. Unknown event/source/timezone evidence is explicitly marked
  descriptive-only and ineligible for strict historical use. Late downloading
  of a correctly dated historical snapshot remains supported.
- **Prices and corporate actions:** automatic adjustment, back adjustment, and
  repair are disabled. Provider OHLC, adjusted close, dividends, and splits are
  stored separately. This does not prove historical tradable raw prices.
  Screening windows with corporate actions require review.
- **Research scope:** authoritative exchange calendars, a corporate-action
  ledger, real-data execution validation, and a complete OOS framework are not
  provided yet. Real observations remain descriptive research inputs, separate
  from the validated synthetic backtest. No strategy returns or model performance
  are claimed from these examples.
- **Screening conventions:** dollar volume approximates mean `close * volume`;
  volatility is the sample standard deviation of simple daily returns multiplied
  by `sqrt(252)`. These are assumptions, not trade-level turnover or a verified
  exchange calendar.
- **Factor attribution:** current French history is a retrieved, possibly revised
  vintage, not verified historical publication information. Adjusted-close ratios
  are a provider total-return proxy. Plain-close research excludes dividends and
  refuses action periods. Monthly returns require an explicit session calendar
  including the prior month; missing endpoints are never silently substituted.
  Price/session conflicts are rejected. Monthly rolling windows retain completely
  missing calendar months. Declared provider-adjusted Close cannot be labelled as
  price-only returns. French normalization is independent of Decimal context;
  its v2 factor cache requires one new online fetch before offline replay.

See [Data Policy](docs/DATA_POLICY.md),
[Backtest Assumptions](docs/BACKTEST_ASSUMPTIONS.md), and
[Phase 2 Acceptance](docs/PHASE_2_REPORT.md) for detailed boundaries and actual
local integration evidence.

## Development Roadmap

| Phase | Scope | State |
|---|---|---|
| 0 | Packaging, configuration, fixtures, engineering checks | Completed locally |
| 1 | Synthetic universe-to-execution vertical slice | Completed locally |
| 2 | Real-data research adapters, cache, universe modes, screening | Completed locally |
| 3 | Kenneth French factors, FF3/FF4, OLS, rolling beta | Accepted for ex-post descriptive research |
| 4 | Baselines, ML, purged time-series validation, OOS comparison | Planned |
| 5 | Portfolio risk, historical FX/CAD, persistent paper accounts | Planned |
| 6 | Dashboard, documentation, product validation, V1.0 release | Planned |

`main` holds the accepted baseline; `phase-2-data-universe` retains Phase 2
development history. Future phases use separate feature branches and require
explicit acceptance. The initial GitHub upload is a development checkpoint,
not a V1.0 release.

The original [Project Plan](docs/PROJECT_PLAN.md) is preserved. Read the
[Development Log](docs/DEVELOPMENT_LOG.md), [Changelog](docs/CHANGELOG.md), and
[AGENTS.md](AGENTS.md) before making changes. Detailed project documentation is
currently maintained in Chinese; code identifiers and this README use English.
