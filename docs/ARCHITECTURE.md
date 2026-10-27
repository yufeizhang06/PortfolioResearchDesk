# Phase 0 架构决策

> Phase 3 已通过用户验收，仅限事后描述性因子研究；R1–R5 均已独立复核。以下文字保留阶段上下文。

## Phase 3 — 因子诊断服务

`factor_config → factor_workflow → factor_data / Phase 2 History → factor_returns →
factor_analysis → factor_reporting`，CLI 仅调用同一服务，不复制数学或取数逻辑。

- 独立 FactorData/ReturnData/AlignedSample；同频日/月期间、百分数一次转换、四因子共同样本。
- FrenchAdapter 复用现有有界 HTTP/重试和不可变缓存；保存读取版本，不创建虚假发布时间。
- NumPy/SciPy/statsmodels/matplotlib 属于可选 factors extra，延迟导入；基础包仍能运行 Phase 0–2。
- OLS 显式截距、秩/条件数/VIF、经典或 HC3 协方差、完整推断与残差诊断；统计失败可审计。
- Rolling 先按名义期间定界再取有效样本，每窗单独拟合；缺失不扩大窗口，未来不改变过去估计。
- 月频按请求边界补齐完整日历月，Rolling 入口也补齐内部缺月；清单与已知报价冲突则阻断。
- 调用方 Decimal 精度不能改变收益/超额收益；固定 28 位上下文。真实 Adj Close 仅为总收益代理。
- 因子单位转换通过精确指数移位独立于 context；v2 缓存不复用旧精度相关值。
  provider_adjusted + close 明确拒绝，provider_ohlc 只标收益代理；OLS 数学函数保持原样。
- JSON/CSV/HTML 与 SVG/PNG、运行目录不可覆盖、最后完成标记，复用 collect_provenance。
- 因子始终为事后描述；交易信号入口明确阻断未验证历史可得性，不改变 Phase 1 执行契约。
- R5：共享质量层按支持的美国交易所本地日及 timestamp_basis 检查日线时间标签；
  已知矛盾隔离，因子收益入口明确拒绝，早于 OLS/Rolling。事件、下载与可用时间各自保留。
  未知事件/来源契约/时区数据库显示 SESSION_TIME_UNVERIFIED，只允许描述性解释；
  不新增供应商依赖、行情 schema 或历史可用性认证。使用现有 ZoneInfo；基础环境缺 IANA 数据时明确降级。
- 真实验收发现 yfinance 惰性 Mapping 元数据；将 dict 检查改为 Mapping，并仅读取身份必需键。
  不枚举可能额外请求的惰性键，不放宽交易所/币种/时区验证。

方法、数值边界及月末日历契约见 FACTOR_RESEARCH.md；不实现 Phase 4 的标签或模型训练。

日期：2026-10-27。单一 Python 可安装项目，目标架构见 `PROJECT_PLAN.md`。
下列 Phase 0–1 决策保留为历史记录；用户现已授权 Phase 2，新增决策见末节。

| 决策 | 原因与影响 |
|---|---|
| Python `>=3.12,<3.13` | 沿用计划书兼容起点，实机为 3.12.14。先验证单一系列，后续扩展需重新检查依赖与 CI。 |
| uv 0.13.6 + `uv.lock` | 实际 PyPI 下载的工具；固定解析结果，`--locked` 阻止无意变更。 |
| 运行时零第三方依赖 | 当前只需 argparse、tomllib、csv、dataclasses、logging；量化库推迟到需要时加入。 |
| TOML + 显式严格字段校验 | 不引入 YAML/Pydantic，仍拒绝未知字段、错误类型、未实现模式。配置只有 Phase 0 字段。 |
| Hatchling + src 布局 | wheel/sdist 标准打包；包内资源随 wheel 发布，独立安装验证防止源码路径掩盖遗漏。 |
| 构建后端加入锁定开发组 | `uv build --no-build-isolation --offline` 使用已锁定后端，避免构建时解析另一套依赖。 |
| 固定手工合成数据 | 不依赖网络、随机数、交易日历或真实供应商；重复输出一致，可用哈希校验内容。 |
| pytest-socket | 测试进程禁止 socket，防止未来意外引入联网测试；子进程仍需单独审查。 |

数据流仅为 `CLI → load_config → summarize_sample → JSON stdout`。
配置不隐式读取环境变量；默认值来自包内 TOML。错误统一继承 `ProjectError`，在 CLI 边界转换为
退出码 2；日志写 stderr，意外 bug 保留 traceback。配置模块和样例模块不依赖 CLI。

样例按 `(market, exchange, symbol, session_date)` 检查重复，保留 UTC 的 `event_time`、
`observation_end`、`available_at`，检查 `event_time == observation_end <= available_at`。
这仅约束内置 fixture；尚无决策时间、订单、标签或历史可得性检测器。
未来仍须落实 `available_at <= decision_at < execution_at`、全局日期划分、purge、折内拟合，
不能把本阶段完整性检查当作回测可信度证明。

选型依据（本轮查阅）：

- [Python 3.12 release schedule](https://peps.python.org/pep-0693/)：安全维护计划至 2028-10。
- [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)：锁与同步语义。
- [pytest 入门](https://docs.pytest.org/en/stable/getting-started.html)：测试安装与执行方式。
- [Ruff 安装](https://docs.astral.sh/ruff/installation/)：项目开发工具安装方式。

具体依赖版本、Python 要求和本机验证结果记录在 `PHASE_0_REPORT.md`，锁文件是精确版本依据。

## Phase 1 — 实际纵向闭环

- `domain.py`：不可变、带 Type Hints 的 AssetId、UniverseSnapshot、PriceBar、Signal、TargetPortfolio、
  OrderProposal、Fill、PortfolioState、EquityPoint；跨模块使用这些契约。
- `market_data.py`：当前仅内置 synthetic reader；显式 session manifest，完整 panel、时间/币种/复权检查。
  此模块不等于完成 Phase 2 Adapter/缓存/真实行情。
- `signals.py` / `portfolio.py` / `execution.py`：纯逻辑分离，可独立测试；不依赖 CLI、报告或供应商。
  信号不直接变成成交，先经过目标配置与整股请求，再由执行层检查现金/风险。
- `backtest.py`：按 session 调度 next-open→close valuation→decision；默认输入可注入，数值结果确定。
- `reporting.py`：唯一报告 I/O 边界，版本化 JSON、CSV 账本、自包含 HTML、完成标记与输入快照。
- `backtest_config.py`：独立 Phase 1 严格 schema；原有 Phase 0 schema 和命令继续兼容。
- 包版本提升 0.2.0；Python/uv/开发工具版本和运行时零第三方依赖策略不变；锁文件由 uv 更新。

金额使用 Decimal；引擎固定 28 位上下文，价格/费用显式舍入到分，避免现金账本浮点误差。
开盘数量只能缩减原收盘请求；二分搜索在实际费用后的 NAV 上检查现金缓冲和单票上限。
无法验证开盘持仓估值时取消批次；无法满足继承的跳空约束时显式阻断。
收盘价格漂移导致的超限作为报告警告，不能宣称目标上限持续得到满足。

此阶段没有新增 ML、公司行为账本、FX、Paper 状态持久化或数据供应商；也没有创建对应空模块。
数学和时间契约、手算、数据性质及限制详见 `BACKTEST_ASSUMPTIONS.md`。

## Phase 2 — 数据与统一股票池研究流

版本 0.3.0，Python 3.12 / uv 0.13.6 保持不变。CLI 只注册参数并调用服务：

```text
research_config -> custom/watchlist/official current directory -> explicit include/exclude
                -> HistoryAdapter -> immutable cache -> quality -> optional screening
                -> UniverseSnapshot + audit bundle
```

`universe build` 与 `data fetch` 共用 `run_research()`；前者在不筛选时无需下载价格，
后者明确获取价格。配置在运行前检查预算、模式、数据种类及路径，报告保存每个筛选决定。
不增加 UI、服务框架、任务队列、ML 或后续阶段空模块。

| 决策 | 原因与影响 |
|---|---|
| 独立 `Observation/History` | 可精确保留供应商小数、缺失值、未知事件时刻和来源；不放松已测试的 Phase 1 可执行 PriceBar 契约 |
| `HistoryAdapter` Protocol | Yahoo 与 CSV/Parquet 产生同一契约；核心筛选不依赖 yfinance/pandas/UI |
| 可选 `data` extra | yfinance 用于真实日线，PyArrow 用于 Parquet；基础 CSV 和合成研究仍只需标准库；动态导入缺失依赖时明确报错 |
| `schema_version=2` TOML | 单独 research 配置，保留旧 Phase 0/1 schema 与 CLI；路径相对配置文件解析，未知字段拒绝 |
| JSON 快照 + SQLite 索引 | 无额外数据库依赖；不可变快照与 SHA-256 固定输入，索引仅查找，不混合 real/synthetic；TTL 与刷新显式 |
| CSV sidecar / Parquet 内嵌元数据 | 不能丢失数据来源、时间和价格口径；本地文件不是自动可信，native schema 可审计且能精确往返 |
| Nasdaq 官方当前目录 | 实际可用的美国市场入口；历史指数不可得时保留 current_snapshot 并阻断 PIT 宣称；不误称 Nasdaq-100 |
| 晚可得拒绝 + 未来扰动测试 | 不依据今天的历史修订和成员身份声称可信 OOS；筛选只校验当时可见数据，未来异常不能改变过去决定 |
| 窗口公司行为需要复核 | 当前三规则是描述性 price-return/liquidity 口径，不假装已经实现总收益、成交和公司行为账本 |

新增模块：data_contracts（质量与契约）、data_adapters（网络/本地边界）、data_cache（快照）、
universe（列表与目录）、screening（纯计算）、research_config、research_workflow、data_cli。
原 domain 的 UniverseSnapshot 只增加有默认值的字段；Phase 1 信号、组合、执行与会计逻辑未改。
reporting 增加公共 provenance 包装供两条流程复用，旧报告逻辑保留。

输出逐资产 CSV+sidecar、四类 JSON 与最后的 run.json；没有完成标记的目录不得当成成功运行。
完成标记的 status 仍可为 partial/failed；不是以“文件存在”代替业务验收。
时间、来源与数学定义详见 `DATA_POLICY.md`；锁定依赖兼容信息、真实探测与验收见 `PHASE_2_REPORT.md`。
