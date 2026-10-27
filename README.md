# PortfolioResearchDesk

本地优先的量化股票研究与投资组合模拟平台，目标是把股票池、行情、信号、组合、回测及虚拟账户
连接成统一、可重复运行的研究流程。**当前版本 0.2.0 / Phase 1** 已实现离线自选股票池到模拟执行、
现金/持仓核算及报告的完整闭环。真实行情、Market/Index/Screening、因子、ML、CAD/FX 和持久化
Paper Account 尚未实现。当前合成结果用于验证工程和会计正确性，不是市场证据或投资建议。
系统不连接券商、不执行真实交易、不承诺收益。

## Phase 1 端到端运行

```powershell
uv run --locked --offline prd backtest run --config configs/example_backtest.toml
# 已安装本项目 .venv 时，无需系统 PATH 或激活脚本：
.\.venv\Scripts\prd.exe backtest run --config configs/example_backtest.toml
# 可手算验证的 100 USD / Top-1 / 每笔费用 1 USD 情景：
uv run --locked --offline prd backtest run --config configs/example_handcheck.toml
uv run --locked --offline prd config validate --kind backtest --config configs/example_backtest.toml
```

流程：Custom user_static universe → typed raw synthetic OHLCV → past-only momentum → Top-K equal
targets → known-close integer order requests → next explicit session open → cash/positions/fees/NAV → reports。
3 只资产、6 个明确列出的合成 session；可配置股票子集、回看长度、Top-K、单票上限、现金缓冲、
固定及 bps 费用、滑点。配置严格拒绝 CAD/FX、PIT 指数声明、真实供应商、行业约束及未实现选项。
数据源限定包内 fixture，尚非通用 CSV Adapter。时间顺序执行不等于完成 Walk-Forward ML 验证。

`outputs/runs/<run_id>/` 保存 config/data 快照、result.json、orders/fills/equity/positions.csv、
自包含 report.html；最后写入的 run.json 才是完成标记。`--output-dir` 可改输出父目录，
`--run-id` 可指定唯一 ID；已有运行绝不覆盖。金额和比率以十进制字符串保存。
相同代码/数据/配置的数值结果一致，Run ID 和生成时间每次不同。
无首次 Git commit 或安装包不含 uv.lock 时，对应哈希为 null，仍记录包版本、源码指纹和完整输入。
详细 schema、时序、费用、手算对照与限制见 `docs/BACKTEST_ASSUMPTIONS.md`。

## Quick Start

在项目根目录执行。需要 Python **3.12.x** 和 **uv 0.13.6**；首次下载工具、依赖需要网络，
运行示例和测试不需要网络、密钥或真实行情。项目只承诺本阶段的 Python 3.12 支持。

### Windows PowerShell

```powershell
# 已安装 Python 3.12 时；若没有 py 启动器，请换成 Python 可执行文件的完整路径。
py -3.12 -m pip install uv==0.13.6
py -3.12 -m uv sync --locked --python 3.12
py -3.12 -m uv run --locked --offline prd --help
py -3.12 -m uv run --locked --offline prd config validate --config configs/example_offline.toml
py -3.12 -m uv run --locked --offline prd demo
py -3.12 -m uv run --locked --offline prd backtest run
```

`uv` 已在 PATH 时，后续直接运行 `uv …` 即可。若机器只有应用附带的 Python，请查看
`docs/PHASE_0_REPORT.md` 中的本机复现方式；不需要修改全局依赖。

### macOS / Linux

```bash
python3.12 -m pip install uv==0.13.6
python3.12 -m uv sync --locked --python 3.12
python3.12 -m uv run --locked --offline prd --help
python3.12 -m uv run --locked --offline prd demo
python3.12 -m uv run --locked --offline prd backtest run
```

若系统禁止向全局环境安装工具，可先创建专用工具 venv 再安装 uv，或参照
[uv 安装文档](https://docs.astral.sh/uv/getting-started/installation/)。

`uv sync` 在项目内创建 `.venv` 并安装本项目，不需要手工激活。`--locked` 会在
`pyproject.toml` 与锁文件不一致时失败；`--offline` 禁止 uv 为运行命令下载内容，
因此首次运行前必须成功执行同步。缓存齐全后可用 `uv sync --locked --offline`。

## 本阶段可用命令

```text
prd --help
prd --version
prd config validate [--config PATH]
prd demo [--config PATH]
prd backtest run [--config PATH] [--output-dir PATH] [--run-id ID]
prd config validate --kind backtest [--config PATH]
python -m portfolio_research_desk --help
```

以上 `prd` / `python` 需从项目 `.venv` 调用，推荐前置 `uv run --locked --offline`。
后续阶段的 `research`、`paper` 等命令尚未提供。

`prd demo` 输出 JSON：Phase、规范化配置、9 行/3 只虚构资产/3 个日期的样例摘要、
SHA-256 与局限性。固定样例无随机生成过程，重复执行内容相同。它不计算投资表现。
日志写入 stderr，JSON 写入 stdout，可以分别重定向。成功退出码为 0；命令、配置或
样例的预期错误为 2，并给出简明说明；意外程序错误保留 traceback，便于排查。

## 配置

以下为 Phase 0 兼容入口；新的 Phase 1 配置见 `configs/example_backtest.toml`。
Phase 1 使用根字段 + universe/account/strategy/portfolio/execution 表，全部字段严格验证；
十进制参数推荐写成字符串（如 `"0.10"`），数值小数也直接解析为 Decimal，不经 float。
调用 `config validate` 时以 `--kind backtest` 明确选择 schema，不隐式猜测模式。

使用 `configs/example_offline.toml`；不传 `--config` 时加载安装包自带默认值，
不读取环境变量或任意当前目录配置。显式路径相对调用者当前目录解析。

| 字段 | Phase 0 允许值 | 用途 |
|---|---|---|
| `schema_version` | 整数 `1` | 标记配置格式；布尔值不视为整数 |
| `mode` | `"offline_sample"` | 明确只读取合成样例 |
| `data_source` | `"synthetic"` | 阻止误用真实供应商 |
| `currency` | `"USD"` | 样例价格单位；不是账户记账币种 |
| `log_level` | `DEBUG/INFO/WARNING/ERROR` | 可省略，默认 `INFO` |

前四项必填；未知字段、错误类型、非法 TOML、CAD 和后续运行模式均拒绝。
V1 的目标账户仍是 CAD；Phase 0 不实现账户，不能将 CAD 金额当成 USD。
配置格式选择 TOML 是当前工程决策，计划书 YAML 是未来目标示例，尚不能执行。

## 开发检查

```bash
uv lock --check --offline
uv run --locked --offline pytest -q
uv run --locked --offline ruff check .
uv run --locked --offline ruff format --check .
uv run --locked --offline prd --help
uv run --locked --offline prd config validate --config configs/example_offline.toml
uv run --locked --offline prd demo
uv run --locked --offline prd config validate --kind backtest --config configs/example_backtest.toml
uv run --locked --offline prd backtest run --config configs/example_backtest.toml
uv build --offline --no-build-isolation --out-dir dist/phase1
uv run --locked --offline python scripts/verify_distribution.py dist/phase1
```

测试由 pytest-socket 禁止 Python socket 访问，全部数据由本地包内资源提供。
pytest 临时文件固定在 `work/pytest-tmp`，每次测试会清理该专用目录；不要在其中保存个人文件。
若切换执行账户遇到权限冲突，可仅对本轮指定
`--basetemp=work/pytest-local -o cache_dir=work/pytest-cache-local`，不必修改系统权限。
最后两步验证 sdist/wheel 构建，并从 **sdist 离线重建 wheel**、在独立 venv 安装、切换到
源码导入路径以外运行 CLI、内置资源及 Phase 1 回测和报告，防止仅在源码目录可运行。
构建使用锁定的开发组中的 Hatchling，`--no-build-isolation` 避免另行解析构建依赖。

GitHub Actions 配置覆盖 Ubuntu/Windows 的 Python 3.12：检出代码、安装工具及锁定依赖后，
上述检查使用离线模式，不访问市场数据源、API Key 或账户。检出和依赖安装本身需要网络；
“离线 CI”指测试与样例执行阶段。远端实际执行状态以 GitHub Actions 为准。
**远程 GitHub Actions 与 Linux 本轮尚未实际验证，不能视为已通过。**

## 数据来源与工程边界

- 数据来源：本项目自建 `resources/synthetic_prices.csv`（Phase 0 的 9 行摘要）和
  `backtest_prices.csv`（Phase 1 的 18 行），配套 session manifest，虚构符号
  `SYN_A/SYN_B/SYN_C`，交易所标为 `SYNTHETIC`。无真实行情、私人持仓或供应商数据。
- `event_time` / `observation_end` 为假设收盘时刻，`available_at` 晚一分钟；全部显式 UTC。
  这些时刻和日期只服务于样例，不是经过验证的真实交易日历或供应商发布时间。
- 样例包含未经复权的虚构 OHLCV，没有分红、拆股、退市或历史指数成分覆盖。
  manifest 必须声明无公司行为；有公司行为或 adjusted 数据则阻断。
  不得称为历史 PIT 数据、无偏回测或样本外证据。
- 尚未连接或验证 yfinance、French Data Library、FX、券商或任何外部市场源。
  后续引入时核查可得时间及授权，受限原始数据保留本地，不默认再分发。
- 数据、密钥和研究输出默认忽略 Git；当前没有密钥需求或 `.env` 加载逻辑。

## 目录与学习入口

```text
src/portfolio_research_desk/   契约、数据、信号、组合、执行、回测、报告、CLI 和配置
configs/                      可编辑 Phase 0 TOML
tests/                        配置、资源、CLI 的离线检查
scripts/                      安装包验证脚本
docs/                         完整原始计划、架构决策、阶段验收和变更记录
.github/workflows/            CI
```

- **可安装包与 src 布局**：测试从安装环境导入代码，减少工作目录掩盖打包遗漏的问题。
- **配置 Schema**：输入契约先于运行；不把拼写错误静默变成默认值。
- **锁文件**：记录工具及传递依赖的精确版本与下载哈希，同一代码得到一致依赖。
- **离线 Fixture**：已知、稳定的小数据，将代码问题与外部接口故障分开验证。
- **时间契约**：未来决策必须满足 `available_at <= decision_at < execution_at`；
  例如 21:01 才可得的收盘数据不能支持 21:00 同价成交。Phase 1 已检查信号可得时间和下一
  session 执行，并测试未来扰动；没有实现模型、标签及完整 Phase 4 反泄漏检测器。
- **CI**：自动重复安装、测试和构建，是后续扩展的质量门槛。

协作先读 `AGENTS.md`、`docs/PROJECT_PLAN.md` 和 `docs/DEVELOPMENT_LOG.md`。
本阶段完成后等待用户确认再进入 Phase 2。
