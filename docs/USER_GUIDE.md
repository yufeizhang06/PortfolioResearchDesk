# User guide — local research and paper operations

This guide uses fixed synthetic fixtures. It verifies software behavior, not
investment performance. `prd` below means an installed console entry point;
from a checkout, prefix it with `uv run --locked --offline`.

## Choose an entry point

1. Install Python 3.12 / uv 0.13.6 and synchronize the lock as in the README.
2. Run `prd doctor`. Add `--require factors --require ml` for the full demo.
   Doctor reads package metadata; the workflows additionally import required
   scientific libraries before reserving output. It does not install anything.
3. Use `prd workspace init --directory work/my-desk` for editable examples.
   Initialization requires a new directory. Spaces in paths are supported; quote them.
4. Run `prd workflow run --config work/my-desk/workflow.toml` for the automated
   synthetic walkthrough. This command creates a new account per run. For a
   continuing account, use the manual lifecycle below with a separate database.

Generated `workflow.toml` supports only `mode="synthetic_demo"`, CAD starting
cash (whole cents), Top-K 1–3, optional factor/ML flags and output location.
It uses a fixed three-asset universe and explicit sessions. The other generated
profiles (`research`, `factors`, `ml`, `backtest`, `paper`) are **independent**
engine profiles: editing them does not change `workflow run`. Use their specific
CLI command to run them. Use `paper.toml` to set account risk/costs at creation.

## Read the result

`workflow run` returns `report_directory` and `index`; open that local HTML file.

| Artifact | Meaning |
|---|---|
| `watchlist.csv/json`, `watchlist-export.csv` | Same identities through import/save/load/export |
| `research.json` | Past-only momentum signals and shared synthetic bar hash |
| `decision.json`, `opening.json`, `closing.json` | Readable Paper inputs with explicit source/times |
| `review-plan.json` | Pending target, order quantities, estimated fees and sizing reasons |
| `historical-usd/baseline/` | Separate synthetic USD backtest; not CAD account performance |
| `account.sqlite3` | Synthetic CAD account and original replay inputs; frozen after completion |
| `paper/account/` | Account, event hash chain, trades CSV, NAV CSV and HTML |
| `account-summary.json` | Cash, holdings, costs, recorded valuation and freshness indicator |
| `factors/diagnostic/` | Optional independent known-answer ex-post factor diagnostics |
| `ml/validation/` | Optional independent synthetic walk-forward/holdout experiment |
| `ml-paper-preview.json` | Optional selected-model pending CAD plan, **zero fills** |
| `provenance.json`, `workflow.json` | Code/dependency information, final component status and file hashes |

`prd workflow check --directory <run>` verifies every artifact, including the
SQLite file and nested reports. Missing, modified, additional files and symlinks
fail verification. The manifest is an integrity inventory, not a digital signature
or strategy certification. A failed run has no final `workflow.json`; inspect it,
then choose a new run ID. Do not mutate an immutable workflow account for daily
use: create a separate account. Provenance/output paths vary between machines;
repeated configurations reproduce numerical results, not necessarily every byte
of SQLite/report metadata.

## Manual paper lifecycle

These commands work from the repository root after creating `work/my-desk`.
They use the exact same synthetic decision, execution and valuation inputs as the
integrated demo. Every command opens/closes SQLite; status in a later process
replays the saved events.

```bash
prd paper init --db work/my-desk/accounts/manual.sqlite3 --config work/my-desk/paper.toml --at 2024-01-02T14:30:00+00:00
prd paper validate-snapshot --snapshot work/my-desk/decision.json
prd paper plan --db work/my-desk/accounts/manual.sqlite3 --snapshot work/my-desk/decision.json --plan-id first --top-k 2
```

Read the returned target weights, cash, orders, estimated fills/costs and reasons.
`PENDING_REVIEW` cannot simulate. Copy the exact returned `plan_hash` into the
following approval command **only after inspecting that proposal**:

```bash
prd paper review --db work/my-desk/accounts/manual.sqlite3 --plan-id first --plan-hash <COPIED_HASH> --approve --at 2024-01-04T21:02:30+00:00
prd paper simulate --db work/my-desk/accounts/manual.sqlite3 --plan-id first --snapshot work/my-desk/opening.json
prd paper value --db work/my-desk/accounts/manual.sqlite3 --snapshot work/my-desk/closing.json --event-id closing-mark
prd paper summary --db work/my-desk/accounts/manual.sqlite3
prd paper status --db work/my-desk/accounts/manual.sqlite3
prd paper export --db work/my-desk/accounts/manual.sqlite3 --output-dir work/my-desk/outputs --run-id first-export
```

Replace `<COPIED_HASH>` before running; it is a placeholder, not shell redirection.
Alternatively use `--reject` at review. No command authorizes a broker order.
The execution snapshot is the explicit next open at `2024-01-05T14:30:00+00:00`;
closing valuation is `2024-01-05T21:02:00+00:00`. A conflicting extra `--at` is rejected.
Identical simulation retries return the saved result without another fill/fee.
Reusing an event ID with different input is an error. A stale approved plan must
be expired/replanned rather than silently changed or approved under an old hash.

For non-synthetic forward Paper inputs, use `data_kind="paper_observed"` and record
when each value was actually known. Those inputs are not accepted as historical
PIT-certified signals. Do not relabel the packaged synthetic identities. There is
no automatic Yahoo-to-Paper conversion: the provider observation contract does
not supply every verified time/calendar/action input required for execution.

## Readable Paper snapshot format

`workspace init` emits complete examples. `paper validate-snapshot` checks their
strict schema without modifying an account; `paper plan/simulate/value` performs
additional account-specific freshness, cash, FX, identity and risk checks.
Validation of a file alone does not mean it can execute.

- Root `schema_version=6`, `purpose` (`decision`, `execution`, `valuation`), `as_of`
  (explicit UTC), `data_kind` (`synthetic` or `paper_observed`), and nonempty `source`.
- `prices`: asset (`MARKET:EXCHANGE:SYMBOL:CURRENCY`), observed/available timestamps,
  decimal-string price, `kind` (`close`, `open`, `mark`), explicit `tradable`, integer
  `volume`, and `adjusted=false`. Raw prices avoid double counting actions.
- `sectors`: asset, name, effective/available timestamps. Missing required sector
  coverage fails risk validation; no invented classification fallback.
- `fx`: observed/available timestamps and decimal-string `cad_per_usd` (CAD for
  **one USD**). Inverse conversion is computed, not supplied as a second rate.
- Decision only: `universe` (ID, as_of, available_at, membership_type, assets),
  `signals` (asset, score, observation_start/end, available_at), and explicit
  `sessions` (date, UTC open/close). Use synthetic or static/current membership as
  applicable; the transport refuses to manufacture `point_in_time` certification.
- Optional decision `target`: `weights` array of `{asset, weight}` and `cash_weight`.
  Weights are decimal strings, sum with cash to one and must pass the account's
  limits. Without a target, the existing conservative Top-K planner constructs it.

Prices/amounts/weights should be strings such as `"12.00"`, not binary floats.
Unknown fields, missing booleans, duplicate identities, NaN/Infinity, non-UTC or
late inputs are rejected. Quotes/FX known after the decision cannot fill a gap.
As in Phase 5, caller-supplied source/timing assertions still require external
verification; an explicit timestamp is not proof of real historical availability.

## Cash, FX and recorded NAV

Use an external deposit/withdrawal and then revalue at the same or later explicit
time. For USD flows or conversions provide the native FX CSV described in
[PAPER_TRADING.md](PAPER_TRADING.md). Amounts are whole cents.

```bash
prd paper cash-flow --db work/my-desk/accounts/manual.sqlite3 --event-id deposit-1 --currency CAD --amount 100 --at 2024-01-05T21:02:00+00:00
prd paper value --db work/my-desk/accounts/manual.sqlite3 --snapshot work/my-desk/closing.json --event-id after-deposit
prd paper convert --db work/my-desk/accounts/manual.sqlite3 --event-id convert-1 --source CAD --usd-amount 10 --fx-csv private/fx.csv --at 2024-01-05T21:02:00+00:00
```

For `convert`, `--usd-amount` always names the USD amount bought (source CAD) or
sold (source USD). Fee assumptions come from the persisted account config.
`summary.last_recorded_valuation` retains the previous mark; `valuation_stale=true`
means economic events occurred afterwards or no mark exists, including same-time
flows/actions. It does **not** check a real-time market clock. Revalue after
conversion. Costs have already reduced cash/NAV; never subtract cumulative fees
again. Account P&L is cost-basis attribution, not tax accounting or a return series
adjusted for external contributions.

## Research, models and universes individually

Offline examples (fixed synthetic inputs, no API key):

```bash
prd universe build --config configs/example_research_offline.toml
prd data fetch --config configs/example_research_offline.toml
prd research run --config configs/example_factors.toml
prd ml run --config configs/example_ml.toml
prd backtest run --config configs/example_backtest.toml
```

Create `private/watchlist.csv` with `market,exchange,symbol,currency`, then:

```bash
prd universe watchlist import --input private/watchlist.csv --output private/watchlist.json --kind real
prd universe watchlist update --input private/watchlist.json --output private/watchlist.json --add US:XNAS:NVDA:USD --remove AAPL
prd universe watchlist export --input private/watchlist.json --output private/export.csv
```

Use `watchlist="../private/watchlist.json"` instead of `assets` in a research profile
under `configs/`. Custom, market and screening modes can be combined with explicit
include/exclude/rules and `data.max_assets` request budgets. Real-data templates
are `example_real_research.toml`, `example_market_research.toml` and
`example_factors_real.toml`; review their dates, identities, rights and network
behavior first. Their actual observations are descriptive research inputs.
`--offline` on those application commands requires valid caches; `--allow-stale`
records an explicit stale-cache decision, not a historical PIT claim. Source
failure never silently switches to synthetic data. See the data/factor guides
for exact normalized CSV sidecars, return conventions and cache policy.

## Errors and local data protection

| Symptom | Action |
|---|---|
| Missing optional extra | Run the doctor-suggested locked sync, then retry with a new run ID if needed |
| Directory/database exists | Reuse the account through status/plan; choose a new workspace/report ID |
| Cash/risk/FX/quote rejection | Read reasons; supply available inputs or create a feasible new plan, review again |
| Pending review or wrong plan hash | Inspect current plan; provide explicit review of its exact hash |
| Changed event ID payload / corrupted ledger | Do not edit SQLite; preserve a copy and investigate using the audit export |
| Report verification fails | Preserve original and changed files; rerun with a new ID, do not overwrite hashes |
| Timestamp error | Supply explicit UTC; distinguish observation, availability, decision and execution |

Generated workspaces ignore runs, accounts, cache, data, outputs and private
folders, common database files and credentials. Put real inputs in `private/` or
`data/`, not beside synthetic templates destined for source control. The root
repository additionally ignores environments, binary tools, distributions,
private observations and common secret types. SQLite is not encrypted or digitally
signed; use trusted local storage and backups. No automatic migration from an
unknown schema or recovery by dropping events is attempted.
