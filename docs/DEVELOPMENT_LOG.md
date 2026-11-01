# Development history

This technical timeline covers the initial implementation through the first GUI
(2026-10-27 to 2026-10-31). It summarizes design decisions, defects and evidence;
the current supported scope is in the [README](../README.md#current-development-status).
Phase reports record their own dated validation boundaries, not current task
instructions. Development includes AI-assisted implementation and separate
agent-run reviews; those reviews do not certify real investment performance.

## Milestones and evidence

| Date | Milestone | Software evidence and limits |
|---|---|---|
| 2026-10-27 | Phase 0: package/config/CLI foundation | 45 local tests, Ruff/lock/build/isolated-install checks; [report](PHASE_0_REPORT.md) |
| 2026-10-27 | Phase 1: synthetic USD vertical slice | 141 local tests; known-answer accounting and next-session execution; details below |
| 2026-10-27 | Phase 2: adapters, universe and screening | 208 tests, real Yahoo/Nasdaq probes and cache replay; current membership is not historical PIT; [report](PHASE_2_REPORT.md) |
| 2026-10-27 | Phase 3: ex-post factor research | Final 330 tests/platform; common-sample FF3/FF4, daily/monthly contracts and review fixes; [report](PHASE_3_REPORT.md) |
| 2026-10-27 | Phase 4: synthetic ML/walk-forward | 425 tests/platform; date-grouped purged folds, train-only preprocessing and frozen holdout; [report](PHASE_4_REPORT.md) |
| 2026-10-28 | Phase 5: CAD/FX and persistent Paper | 609 tests/platform; exact-hash review, atomic events/replay and restart/idempotency; [report](PHASE_5_REPORT.md) |
| 2026-10-28 | Phase 6: product integration | 689 tests/platform; offline workspace/workflow, readable inputs and independent installations; [report](PHASE_6_REPORT.md) |
| 2026-10-29 to 2026-10-31 | Phase 7: shared reports and first GUI | Windows 742 / Ubuntu 741 passed + 1 skip at `88f1104`; [report](PHASE_7_REPORT.md), [publication evidence](PUBLICATION_REVIEW.md) |

All counts refer to the revisions and scopes in the linked reports. Later phases
extend earlier software; earlier statements of missing features describe their
dates. The original [project plan](PROJECT_PLAN.md) remains a design reference,
not a completed feature checklist or a real PIT/OOS certification.

## Significant defects and design decisions

- **Portable testing and packaging:** initial Windows temporary-directory ownership
  issues were resolved with writable isolated test directories. Commit `1a4dfae`
  removed a checkout-specific pytest temp setting after fresh CI exposed it.
  Distribution checks rebuild the sdist and install both wheels outside the source
  tree so editable/source imports cannot hide missing resources.
- **Phase 3 installation:** run `40597082932` exposed missing locked scientific
  wheels in the isolated-install cache. Commit `139d17f` reused the locked wheel
  cache; subsequent exact-SHA checks passed. This was an installation fix, not a
  statistical-method change.
- **Phase 3 review fixes:** R1–R5 tightened price/adjustment semantics, Decimal
  normalization, monthly nominal grids/session manifests, rolling-window coverage
  and daily session-time consistency. Self-consistent fabricated provenance still
  cannot be certified by field validation. Full counterexamples and limitations
  remain in the [factor report](PHASE_3_REPORT.md).
- **Phase 4 temporal evidence:** 144 parameter combinations / 3,024 boundary folds
  were software boundary checks, not market trials. Five-model validation-label
  and holdout perturbation tests verify development isolation. Synthetic holdout
  fixtures were repeatedly used for software development, so they are not evidence
  of an untouched real research holdout.
- **Phase 5 review fixes:** high fixed-fee sale feasibility, mixed synthetic/real
  inputs, simultaneous corporate actions, valuation freshness and native input
  validation were corrected and retained as regressions. Separate-agent review
  included Fraction checks and concurrent repeated execution; see the report for
  exact scope and evidence.
- **Phase 6 integration:** retain schema 5 native inputs while adding readable
  schema 6 transport; keep the fixed synthetic demo separate from editable daily
  accounts. NAV becomes historical after a later economic event, even at the same
  timestamp. Optional factors/ML remain distinct evidence; the selected ML preview
  produces no fills. [Review provenance and public checks](PHASE_6_CODE_REVIEW.md).
- **Phase 7 presentation:** reuse recorded financial results through shared report
  formatters and a UI-independent service layer. GUI coverage is intentionally
  smaller than the CLI. No second financial engine, broker or Paper write wizard
  is introduced. [Architecture](ARCHITECTURE.md), [GUI guide](GUI_GUIDE.md).

## Phase 1 implementation and local acceptance — 2026-10-27

The following preserves the original vertical-slice technical evidence, which has
no separate Phase 1 report. All prices/results are synthetic USD software tests.

### Implemented behavior

- 版本 0.2.0；不改变 Python 3.12 / uv 0.13.6 / 开发工具版本，运行时依赖仍为标准库。
- AssetId、UniverseSnapshot、PriceBar、Signal、TargetPortfolio、OrderProposal、Fill、PortfolioState
  等不可变契约；完整身份、UTC、币种、整股、价格和数据可得时间检查。
- 3 资产 × 6 个显式 session 的独立合成 fixture；完整 panel、禁止 adjusted 和未处理公司行为。
- 自选静态股票池、确定性过去窗口动量、Top-K 等权、现金和单票上限、收盘整股请求。
- 下一 session raw open 执行、先卖后买、固定/bps 费用、不利方向滑点舍入、现金与仓位限制缩单。
- 每日持仓/现金/NAV、回撤、费用/滑点、成交额比率及零利息现金基准。
- 不可覆盖的运行目录、完整输入快照、代码/数据/配置/依赖锁指纹、JSON/CSV/HTML、完成标记。
- 旧 Phase 0 命令兼容；新增 backtest run / config validate --kind backtest。
- CI 及独立安装验证扩展到 Phase 1；没有把尚未运行的远端工作流写成通过。

### 实际测试与验收

- 全量 pytest：**141 passed**（包含原有 45 个测试）。
- Ruff lint、format 检查通过；uv lock 离线一致性检查与 0.2.0 锁定安装成功。
- 默认 CLI：10 笔合成成交，运行目录 `outputs/runs/phase1-validation/`，9 个完成文件。
- 手算 CLI：100 USD → NAV `[100,100,99,89,87,90]`，7 笔成交，费用 7，
  终现金 10、A 5 股，-10% 合成累计收益、13% 最大回撤；
  运行目录 `outputs/runs/phase1-handcheck/`。不是历史市场研究结果。
- sdist + wheel 构建成功；从 sdist 离线重建 wheel 成功；两种 wheel 的独立 venv 安装、
  CLI 帮助/Phase 0 资源/Phase 1 回测与报告全部通过。
- 测试包括：未来价格扰动、晚可得输入、同日执行拒绝、决策请求不使用下一开盘增仓、
  整股/资金不足/跳空/实际成本后上限、独立账本重建、停牌/缺失开盘、非法数据与配置、
  公司行为/复权/PIT/跨币种拒绝、报告不可覆盖及 I/O 失败完成标记。

历史验收命令（当前安装与完整检查以 [README](../README.md) 为准）：

```text
uv lock --check --offline
uv run --locked --offline pytest -q --tb=short --basetemp=work/phase1-tests -o cache_dir=work/phase1-pytest-cache
uv run --locked --offline ruff check .
uv run --locked --offline ruff format --check .
uv run --locked --offline prd --help
uv run --locked --offline prd --version
uv run --locked --offline prd config validate --kind backtest --config configs/example_backtest.toml
uv run --locked --offline prd backtest run --config configs/example_backtest.toml --run-id phase1-validation
uv run --locked --offline prd backtest run --config configs/example_handcheck.toml --run-id phase1-handcheck
uv build --no-cache --offline --no-build-isolation --out-dir dist/phase1
uv run --locked --offline python scripts/verify_distribution.py dist/phase1 --uv <本机 uv 可执行文件>
```

再次运行时使用新的 Run ID；已有目录不会被覆盖。原验收使用独立的本地 uv 缓存。
尝试用 no-build-isolation 做 editable 同步时发现 Hatchling 的 editables 构建要求不在当前环境；
按 README 的正常隔离 `uv sync --locked --offline` 即成功，不为临时构建方式改动依赖集合。
发行包构建仍使用锁定的 Hatchling 及 no-build-isolation，已实际通过。

### Validation boundaries at that date

- Remote Actions and Linux/macOS had not yet been exercised for this initial
  local slice. Later platform results are recorded at their exact revisions.
- Only synthetic raw cent prices and USD accounting were supported; CAD/FX,
  persistent Paper, ML and provider adapters were added in subsequent phases.
- Execution constraints are checked at fills; later price drift may produce
  closing concentration warnings. Infeasible inherited opening risk fails closed.
- Six synthetic sessions do not support annualized/Sharpe or investment claims.

## Source-control and CI provenance

The initial commit `86dc682` contains the Phase 0/1 foundation. Later phase
branches and original commits are retained. Runs were observed through
`workflow_dispatch`; the reports do not claim that an unobserved push trigger ran.
Failures are retained as development evidence rather than hidden from history.

Functional acceptance runs include [Phase 3](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40598369112),
[Phase 4](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40602662692),
[Phase 5](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40759391233),
[Phase 6](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40793091056)
and [Phase 7](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/41175396204).
The Phase 7 documentation revision `a1a6863` has its own
[run 41176056821](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/41176056821).
These are dated evidence, not CI results for later edits.

The project uses MIT for original code and synthetic fixtures. External software
and data rights remain separate. Real observations, local accounts, review tools,
raw logs and generated reports remain outside source control; public summaries
preserve commands, hashes and result boundaries where available.
