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

## 2026-10-27 — Phase 2 开始（用户已授权）

- 已核实首次提交为 `86dc6824efa0754aa53e4b5263c4352113339d0c`，起点工作区干净、无远端。
- 建立本阶段分支 `phase-2-data-universe`；AGENTS 标明仅授权 Phase 2，完成后停止。
- 完整阅读项目计划、README、协作规范、阶段记录及已实现代码；基线 141 测试通过，无功能阻塞。
- 目标按 Phase 2：真实/本地 Adapter、缓存与质量、三种 Universe 与组合筛选；
  保留旧合成回测，真实下载只用于带覆盖限制的描述性研究，不引入后续因子/ML/账户。
- 来源核实：Yahoo 经第三方 yfinance，不是官方交易所行情；Market 首发 Nasdaq 官方当前目录，
  无历史指数成分与退市覆盖。精确历史发布时间未知，禁止虚构。

## 2026-10-27 — Phase 2 完成，等待用户验收

### 已完成

- 版本 0.3.0；Python 3.12 / uv 0.13.6 保留，可选 data extra 与真实 uv.lock 解析。
- 独立 Observation/History 契约；真实数据、synthetic、来源/UTC/复权/公司行为明确分开。
- yfinance 真实日线、native CSV + checksum sidecar、Parquet 元数据与精确数值往返。
- 真实 retrieved_at 作为可得时间；日线 event_time 未知，使用明确标注的本地日期上界。
- SQLite 索引 + 不可变 SHA-256 快照；TTL、offline、refresh、allow-stale、损坏检测与显式修复。
- 有界超时/重试、HTTP-date/numeric Retry-After、限流停批、缺失/schema/身份错误及逐资产失败。
- 自选列表导入/导出/保存/读取/更新/去重；官方当前市场目录及成员过滤原因。
- 流动性、价格动量、历史波动率、历史长度筛选；三模式及 Market/Custom + Screening。
- current_snapshot/user_static/未验证 PIT 显式契约与历史阻断；未来扰动、晚可得输入测试。
- 统一 CLI/服务研究流程、质量/筛选/缓存与输入指纹报告、逐资产 CSV 和最后完成标记。
- README、DATA_POLICY、ARCHITECTURE、CHANGELOG、PHASE_2_REPORT 与 CI/安装验证更新。

### 实际测试与验收

- **208 passed**（原 141 测试保留），最终独立临时目录运行无警告；测试 socket 被禁止。
- Ruff lint / format、uv lock 检查、锁定 data extra 安装、新旧 CLI/配置/默认样例通过。
- wheel/sdist 构建、sdist 离线重建、直接与重建 wheel 干净 venv 安装及源码外 Phase 0/1/2 运行通过。
- 真实 Yahoo AAPL/MSFT 各 18 日观测；官方目录保留 4,328、排除 1,297（当前目录，不是普通股全集）。
- Custom / Market 组合筛选真实运行 complete；目录 + 两资产离线缓存 3/3 命中。
- 真实 CSV→Parquet→读取精确一致，CLI check 通过；数据与原始证据均在 Git 忽略目录。
- 初次旧 pytest 缓存有权限警告，独立本轮目录后消除；首次构建临时目录写失败，
  经批准以普通本机权限重跑成功。yfinance 上游 Pandas4Warning 保留并记录。
- 完整命令、哈希、来源与实际证据位置见 `PHASE_2_REPORT.md`，不把接口模拟测试当真实下载。

### 限制与下一阶段

- GitHub Actions 仅配置更新，**远程未验证**；Linux/macOS 未实机验证。
- 真实数据没有历史 PIT/权威日历/退市/身份演变保证，不声称幸存者偏差已解决或可信 OOS。
- 无任意格式 CSV 自动映射、市值/行业筛选、真实回测、公司行为账本、FX、因子、ML 或持久账户。
- Phase 1 业务和数据入口保持 synthetic；真实 History 不被放入已测试的可执行 PriceBar。
- 原始项目计划未改；本阶段变更未自动提交或 Push，没有远端修改或真实交易。
- 建议提交：`feat: add market data adapters, cache and universe screening`。
- Phase 3 依赖可靠的频率/单位/日期/来源契约及诊断性边界；用户明确确认前不启动。

## 2026-10-27 — 用户验收 Phase 2，授权首次 GitHub Private 上传

- 用户已查看并确认 Phase 2 本地验收；本轮范围仅本地提交、英文 README、Private 仓库初始上传及 CI。
- 保留首次提交 `86dc6824efa0754aa53e4b5263c4352113339d0c` 和现有阶段分支；不重写历史。
- README 改为英文，列明 Overview、Features、Status、Architecture、Installation、Quick Start、
  Testing、Structure、Data Limitations、Roadmap；版本保持 0.3.0，不宣称产品或真实回测已完成。
- 原始 PROJECT_PLAN 和既有开发历史保留；AGENTS 仅更新当前授权范围，Phase 3–6 仍未授权。
- 重新执行 208 测试、Ruff lint/format、uv.lock 一致性及锁定 data extra 安装，全部通过。
- 提交前门槛还包括三种配置验证、默认离线流程、构建/独立安装、候选文件与历史敏感模式检查。
- 本地原先无 Remote；官方便携版 gh 2.103.3 下载并通过官方 SHA-256 校验，工具只在忽略的 work/。
- 用户通过 GitHub 官方设备授权完成登录；账号为 yufeizhang06，未发现 PortfolioResearchDesk 同名仓库。
- 目标为 Private `yufeizhang06/PortfolioResearchDesk`，main 保存已验收版本，保留 phase-2-data-universe；
  不创建 V1.0 Release。实际 Push 和远端 CI 结果在完成后另行补记，不将本地通过当成远端通过。

## 2026-10-27 — 首次 Push 与真实 CI 问题修复

- Phase 2 Commit：`471b6a253246dd7daa2a326a503c7c02faca00cf`，35 个修改文件，完整版本树 69 文件。
- 已创建 Private https://github.com/yufeizhang06/PortfolioResearchDesk，描述按用户原文设置。
- main 与 phase-2-data-universe 首次普通 Push 成功，原始历史保留；两远端提交及文件树与本地一致。
- Actions 已启用。首次 Push 后未观察到自动运行记录，故在 main 显式 workflow_dispatch 触发现有 CI。
- 首次真实 CI：https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40543680987。
  Ubuntu/Windows 都在测试准备阶段失败，Ubuntu 为 105 passed / 103 setup errors。
- 根因：pyproject 强制 --basetemp=work/pytest-tmp，但 work 被忽略，全新 checkout 没有父目录，
  pytest 创建该目录时未递归创建父目录。本地已有 work，先前测试未暴露此条件。
- 修复使用 pytest 默认平台临时目录，并更新 README；没有删除或放宽测试，也不改业务逻辑。
- 此处保留首次失败记录；后续修复验证和 CI 状态另行补记，不将失败重写为通过。
- 干净副本复验：无 work 目录开始，离线锁定安装、默认临时目录策略下 **208 passed**、Ruff
  lint/format、默认研究流程全部通过；uv.lock 检查仍通过。未创建额外业务模块或放宽测试。
- 本机旧系统 pytest 临时目录有权限残留，验证用任务专用短临时根目录（PYTEST_DEBUG_TEMPROOT），
  不改系统权限、不删除其他目录，也不在项目配置里写入本机绝对路径；远端使用平台默认目录。

## 2026-10-27 — GitHub Private 初版与跨平台 CI 验证完成

- 仓库：https://github.com/yufeizhang06/PortfolioResearchDesk，Visibility 为 PRIVATE，默认分支 main。
  Description 按用户原文设置；没有配置或改动其他仓库，没有创建产品 Release。
- 业务阶段提交 `471b6a253246dd7daa2a326a503c7c02faca00cf`；CI 修复提交
  `1a4dfaefe2c5fc1a213fc2acd7bbcd277e411abf`；首次提交及两个阶段分支的历史均完整保留。
- 修复后的真实 CI：
  https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40544579916，conclusion=success。
  Ubuntu/Python 3.12.15：208 passed；Windows/Python 3.12.10：208 passed。
  两平台均完成 Ruff、帮助/配置/离线研究/合成回测、构建、sdist 重建及独立 wheel 安装检查。
- 本次使用现有 workflow_dispatch 入口实测；首次 Push 后未观察到自动运行，不宣称已验证 push 触发链路。
- CI 保留了上游 Node.js 20 弃用与 Ubuntu runner 镜像迁移提示，未导致失败；后续可单独维护 Actions
  版本，不为隐藏警告随意调整已锁定 Python 依赖。macOS 仍未实机验证。
- 原始计划 SHA-256 保持不变；英文 README 十个要求章节及相对文档链接均通过检查。
- 上传前审核 69 个版本文件、35 个 Phase 2 改动与首次提交的 46 个历史文件版本，敏感模式未检出。
  .env/密钥、venv、行情、缓存、输出、便携工具和构建产物均未进入版本树。
- README、AGENTS、CHANGELOG 和验收报告补充真实远程状态；作为独立文档提交收尾，保持 0.3.0。
- main 与 phase-2-data-universe 保留并同步发布；不 force push、不重置、不执行真实交易。
- 下一阶段建议仍为 Phase 3 因子诊断；当前没有开始，等待用户确认。
