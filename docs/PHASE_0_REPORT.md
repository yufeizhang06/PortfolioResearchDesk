# Phase 0 实施与验收记录

日期：2026-10-27（America/Toronto）。范围：仅 Phase 0。
本文件保留 Phase 0 的历史验收状态；当前安装和功能范围见 [README](../README.md)，
后续阶段证据见[开发历史](DEVELOPMENT_LOG.md)。

## 初始检查

- 初始项目目录为空；建立包、CLI、配置、测试和文档基础。
- 下载版计划书全文 864 行，已完整阅读并原样复制为 `docs/PROJECT_PLAN.md`。
- 原件/副本 SHA-256 均为
  `1F208C70B41AEAECFAC45F1E38BCD2D3FF674F6EB1868352B45FD9EB40F752BB`。
- PATH 没有 `python`、`py`、`uv`、`pytest`、`ruff`；应用附带 Python 为 3.12.14。
- 初始化本地 `phase-0-foundation` 分支；没有 commit、push 或 GitHub 远端配置。

## 已实现清单

- [x] `pyproject.toml`、`uv.lock`、Python 版本范围、可安装 src 布局。
- [x] `prd --help/--version`、`python -m portfolio_research_desk`。
- [x] 严格 TOML 配置、默认包内资源、stdout JSON/stderr 日志、预期错误退出 2。
- [x] 3 个虚构资产 × 3 个日期 = 9 行自建 OHLCV；无网络、密钥或随机状态。
- [x] pytest、Ruff、GitHub Actions 的 Windows/Ubuntu 离线执行步骤。
- [x] sdist/wheel 构建、sdist 离线重建 wheel、独立 venv 安装与目录外 CLI/资源验证。
- [x] README Quick Start、AGENTS.md、架构决策、CHANGELOG、忽略规则。
- Phase 1 在后续实现；此处仅记录 Phase 0 验收范围。

## 环境与版本选择

| 工具 | 实际版本 | 安装元数据中的 Python 要求 | 选择说明 |
|---|---|---|---|
| Python | 3.12.14 | 项目仅 `>=3.12,<3.13` | 沿用计划书起点，使用现有解释器 |
| uv | 0.13.6 | 独立工具 | PyPI 实际下载，工具版本也固定 |
| Hatchling | 1.32.4 | `>=3.10` | 标准打包；构建后端精确固定并列入开发锁 |
| pytest | 9.1.1 | `>=3.10` | 配置、边界、CLI 与资源验证 |
| pytest-socket | 0.8.1 | `>=3.10` | 禁止测试进程发起 socket 请求 |
| Ruff | 0.17.3 | `>=3.7` | Lint + 格式检查 |

以上来自真实解析、安装元数据和 Windows 实际运行；不代表已验证所有平台。
运行时无第三方依赖，开发及传递依赖完整版本/平台文件哈希见 `uv.lock`。
Python 3.12 官方维护计划见 `ARCHITECTURE.md` 中官方链接，未追求“最新版本”。

## 本机启动

桌面文件夹验收后可直接调用虚拟环境，无需系统 PATH 或激活脚本：

```powershell
Set-Location '<repo>'
.\.venv\Scripts\prd.exe --help
.\.venv\Scripts\prd.exe config validate --config configs/example_offline.toml
.\.venv\Scripts\prd.exe demo
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
```

原验收使用 Git 忽略的本地 uv 工具和已有 Python 3.12 解释器。新安装应使用
[README](../README.md#installation--quick-start) 的公开流程，例如
`uv sync --locked --python 3.12`；首次无缓存同步需要网络。
`<repo>` 表示当前 clone 根目录，项目不依赖开发机器的缓存运行时布局。

## 实际验收

临时工作区已执行且通过：

| 命令 | 实际结果 |
|---|---|
| `uv sync --locked --python <现有 Python>` | 成功安装项目与锁定开发依赖 |
| `uv lock --check --offline` | 成功 |
| `uv run --locked --offline pytest -q` | 45 passed，无未处理警告 |
| `uv run --locked --offline ruff check .` | All checks passed |
| `uv run --locked --offline ruff format --check .` | 成功 |
| `uv build --offline --no-build-isolation` | sdist 和 wheel 均成功 |
| `uv run --locked --offline python scripts/verify_distribution.py dist --uv <工具路径>` | 从 sdist 重建 wheel，两种 wheel 的独立安装和 CLI/包内资源均 PASS |

桌面最终目录已实际复核通过，命令中的 `uv` 使用 `work/bin/uv.exe`：

| 命令 | 实际结果 |
|---|---|
| `uv sync --locked --offline --python <现有 Python>` | 在桌面新建 `.venv` 并离线安装成功；后续重新同步成功 |
| `uv lock --check --offline` | 成功，13 个包的解析记录一致 |
| `uv run --locked --offline pytest -q --tb=short` | **45 passed in 0.42s** |
| `uv run --locked --offline pytest -p pytest_socket -q --tb=short`（关闭插件自动加载） | **45 passed in 0.36s**，验证 CI 命令 |
| `.venv/Scripts/python.exe -m pytest -q --tb=short` | **45 passed in 0.36s**，验证本机 README 入口 |
| `uv run --locked --offline ruff check .` | All checks passed |
| `uv run --locked --offline ruff format --check .` | 16 files already formatted（包含 Ruff 识别的配置文件） |
| `uv run --locked --offline prd --help` | 退出 0，展示 config/demo 命令及 Phase 0 边界 |
| `uv run --locked --offline prd config validate --config configs/example_offline.toml` | 退出 0，输出规范化 JSON 配置 |
| `uv run --locked --offline prd demo` | 退出 0，9 行 synthetic/USD 元数据 |
| `uv build --offline --no-build-isolation` | sdist + wheel 构建成功，无缓存目录警告 |
| `uv run --locked --offline python scripts/verify_distribution.py dist --uv <工具路径>` | sdist 重建、两种 wheel 独立安装、目录外 CLI/配置/资源均 PASS |

真实命令输出保存在本地 `work/phase0-verification-final.log`（Git 忽略）。
合成 CSV SHA-256 为 `c46a3e454b529eea41d0633586b4128383e89c3697e9851dd038352e431ab913`。

修改文件清单（全部为本轮新建）：

```text
.gitattributes  .gitignore  .python-version  .github/workflows/ci.yml
pyproject.toml  uv.lock  README.md  AGENTS.md
configs/example_offline.toml
docs/PROJECT_PLAN.md  docs/ARCHITECTURE.md  docs/CHANGELOG.md  docs/PHASE_0_REPORT.md
src/portfolio_research_desk/{__init__,__main__,cli,config,errors,sample}.py
src/portfolio_research_desk/resources/{default.toml,synthetic_prices.csv}
tests/{test_cli,test_config,test_sample}.py
scripts/verify_distribution.py
```

测试涵盖缺字段、未知字段、非法 TOML/编码/类型、不可变配置、CAD/模式/数据源拒绝、
资源缺失/损坏/空数据/重复/异常 OHLCV/时间戳、错误退出码及 stdout/stderr 边界。
pytest-socket 本身的预期警告由测试显式断言，不全局屏蔽警告。

原验收期间发现缺少 PATH 工具、Ruff 换行错误和临时目录权限问题，修正后复查通过；
未为单个警告调整整个 Python 环境。首次 pytest 因临时目录权限出现 11 passed / 34 setup errors，
将 pytest 临时目录明确配置为项目 `work/pytest-tmp` 后重新验收；该目录每次测试会清理。
临时构建曾提示缓存处于源码树内；sdist 明确限制收录目录，最终目录构建缓存放在项目外，
并检查分发包中没有 work、缓存或私密文件。

## 差异、限制和下一阶段依赖

- 计划书 YAML 是目标示例；Phase 0 选择 TOML + 标准库严格校验，减少依赖，未改变未来产品目标。
- 原始计划书任务框保持规划状态；本文件单独记录 Phase 0 的实际完成范围。
- 没有占位未来命令、空 domain 模块、ML/策略/回测/账户/FX/UI/真实订单。
- 合成 UTC 21:00/21:01 是 fixture 假设，不是真实日历/发布时间验证；没有完整反泄漏检测器。
- 尚未验证 yfinance、French 因子、FX 或其他外部数据源；没有真实投资表现。
- GitHub Actions 配置已编写；远端工作流尚未执行，不能宣称已通过。Linux 本轮未实机运行。
- 当时的后续设计为离线最小信号→等权→下一交易日模拟成交→现金/净值与手算对照；
  后续实现结果见[开发历史](DEVELOPMENT_LOG.md#phase-1-implementation-and-local-acceptance--2026-10-27)。
