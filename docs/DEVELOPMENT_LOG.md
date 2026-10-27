# Development Log

## 2026-10-27 — Phase 1 开始（用户已授权）

- 已完整阅读计划书、AGENTS、README、源码与 Phase 0 验收记录。
- 实际状态：只有 Phase 0 配置、CLI、合成数据摘要；没有回测或后续研究模块。
- Git 尚无首次提交、没有远端；GitHub Actions 仅有配置，未远程执行。
- 本轮默认 pytest 临时目录遇到执行账户权限冲突；使用独立本轮临时目录复核。
- Phase 1 目标：离线自选股票池→动量 Top-K 等权→下一样例交易日开盘成交→整数股、
  现金、费用、净值→JSON/CSV/HTML；手算、未来扰动与异常路径验证。
- 保留 Phase 0 命令兼容性；不引入真实数据、ML、CAD/FX、持久化 Paper 或 Dashboard。
- Phase 0 独立目录复核实际为 45 passed / Ruff lint 与格式检查通过。

## 2026-10-27 — Phase 1 完成

用户在开发中再次确认：真实数据留待下一阶段，本轮继续完成合成数据闭环。

### 已实现

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

本地可复现命令（`uv` 可换成项目内 `work/bin/uv.exe`）：

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

上述两个固定 Run ID 已存在，再次运行请省略 ID 或换新 ID；重复 ID 会正确报错。
本轮因旧缓存属于另一账户，uv 检查使用本地 `work/uv-cache-phase1`，没有修改全局环境。
尝试用 no-build-isolation 做 editable 同步时发现 Hatchling 的 editables 构建要求不在当前环境；
按 README 的正常隔离 `uv sync --locked --offline` 即成功，不为临时构建方式改动依赖集合。
发行包构建仍使用锁定的 Hatchling 及 no-build-isolation，已实际通过。

### Git 与未解决问题

- 当前分支 `phase-1-vertical-slice`。仓库尚无首次 commit，因此所有源码仍未提交；
  没有删除历史、重置改动、配置远端、自动提交、push 或公开仓库。
- 建议首次提交消息：`feat: add offline portfolio backtesting vertical slice`。
  当前首次提交会同时收录 Phase 0 基础与 Phase 1 实现；后续每阶段保持独立提交。
- **远程 GitHub Actions 未执行；Linux/macOS 未实机验证**。本机验证不能替代这些状态。
- 数据全为自建 synthetic，当前没有官方行情接口、真实市场研究结果或真实账户。
- 仅 USD、raw cent prices；无 FX/公司行为处理/行业约束/持久化 Paper/ML。
- 执行时检查上限，持仓后价格漂移的收盘超限报告警告；继承的开盘跳空约束不可行时显式阻断。
- 年化指标不适用于此 6-session fixture；不展示 Sharpe 或夸大可投资性。
- 无本阶段阻塞性功能问题；上述为明确边界与后续待验证事项。

### 下一阶段建议（未实施）

Phase 2：按计划接入真实数据和通用本地 Adapter、缓存、质量报告，扩展三种 Universe 模式和
Screening。接入前逐项核实来源是否官方、授权、时间可得性、复权及公司行为、PIT 覆盖。
用户明确确认前不启动。当前阶段停止在 Phase 1。

## 2026-10-27 — 首次本地 Git 提交检查

- 用户明确授权首次本地提交，消息为：
  `feat: establish project foundation and initial backtesting pipeline`。
- 当前阶段分支为 `phase-1-vertical-slice`；提交范围覆盖 Phase 0 基础与 Phase 1 离线回测流水线。
- 审核 46 个项目文件，包括 AGENTS、原始计划、开发记录、README、架构/验收说明、源码、测试、
  配置、uv.lock、pyproject 与 CI。没有二进制或超过 1 MiB 的待提交文件；最大文件为项目计划。
- 所有候选文本按私钥、常见访问令牌、URL 内嵌凭证及敏感赋值模式扫描，未发现疑似凭证。
  这是本地规则检查结果，不代表对未来新增内容的保证。
- gitignore 补充常见凭证文件名、证书容器、缓存、日志和研究数据/模型格式；
  32 项排除检查与 11 项必要文件/模板保留检查通过。只有两份明确为 synthetic 的小型 CSV 被纳入。
- 本轮不改业务逻辑：对源码、测试、配置、安装包验证脚本、pyproject 和锁文件共 34 个文件
  记录 SHA-256 并复核一致。Phase 1 最近一次实际结果仍为 141 passed，本轮未新增业务变更。
- 原始计划书的 Markdown 行末双空格保留不改；仅为该文件设置 Git whitespace 属性，
  避免将明确的 Markdown 换行语法误报为普通文本尾随空白。
- 用户已提供作者姓名和 GitHub noreply 邮箱；本次仅在当前仓库配置该身份，不修改全局配置。
- 提交的实际 Hash 以 Git 日志为准，不写入它自身包含的文档，避免自引用。
- 本轮仅本地版本管理；无远端配置、Push、公开仓库或破坏性操作，未进入 Phase 2。
