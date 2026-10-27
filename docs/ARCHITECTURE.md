# Phase 0 架构决策

日期：2026-10-27。单一 Python 可安装项目，目标架构见 `PROJECT_PLAN.md`。
下列 Phase 0 决策保留为历史记录；用户现已授权 Phase 1，新增决策见下节。

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
