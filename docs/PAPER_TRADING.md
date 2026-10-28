# Phase 5：CAD / FX / Paper Portfolio

版本 0.6.0；只管理本地虚拟账户。没有券商、真实订单、自动定时任务或付费服务。
旧 Phase 1/4 USD Backtesting API 继续保留，新 CAD 历史验证和 Paper 共用纯计算。

## 使用流程

默认配置 `configs/example_paper.toml`：3,000 CAD，最多10只、单票20%、行业40%、
现金至少5%、单笔成交额不超过初始批次 NAV 的25%、单批次总成交额/NAV不超过1。
成本为情景参数，绝不是任何券商报价。余下资金留现金，不强行重新分配到风险上限。

```text
uv run --locked --offline prd paper sample --output-dir outputs/paper-inputs/example
uv run --locked --offline prd paper init --db outputs/paper/manual.sqlite3 --at 2026-01-05T14:30:00+00:00
uv run --locked --offline prd paper propose --db outputs/paper/manual.sqlite3 --input outputs/paper-inputs/example/decision.json
```

检查 stdout JSON 中的 `plans.sample-plan.plan`：信号来源、原/目标权重、参考价格、固定整股请求、
下一 session、预估费用与换汇腿、调仓前后行业/现金/风险及缩单原因。
取同一记录的 `plan_hash` 填入以下命令；这是对**精确计划内容**的审核。

```text
uv run --locked --offline prd paper review --db outputs/paper/manual.sqlite3 --plan-id sample-plan --plan-hash <从propose读取的hash> --approve --at 2026-01-05T21:03:00+00:00
uv run --locked --offline prd paper simulate --db outputs/paper/manual.sqlite3 --plan-id sample-plan --input outputs/paper-inputs/example/execution.json --at 2026-01-06T14:30:00+00:00
uv run --locked --offline prd paper status --db outputs/paper/manual.sqlite3
uv run --locked --offline prd paper export --db outputs/paper/manual.sqlite3 --run-id manual-review
```

`--reject` 记录拒绝；`paper expire --db ... --plan-id ... --at ...` 将错过计划开盘的待办计划标记 EXPIRED。
审核必须早于成交；同一时刻审核/成交也不允许。到期后不能补签历史审核。
`paper demo --db <新文件> --run-id <新ID>` 一条命令运行固定合成演示，包含显式标记的脚本审核，
用于验证软件，不是日常人工审核的替代。已有数据库、输入文件及报告目录不覆盖。

状态转换：`PENDING_REVIEW → APPROVED → SIMULATED / REJECTED`；
待审可直接 REJECTED，待审/已审错过开盘可 EXPIRED。每计划内的订单一起成功或一起拒绝。
没有自动调整已审核股数、部分成交、限价单、订单重试撮合或真实执行模式。
改变计划、账户余额、费用或审核内容必须使用新请求；旧计划过时后执行会持久记录拒绝原因。

stdout 是 JSON，诊断 stderr；输入错误退出2。模拟业务拒绝也返回 JSON、退出2，
但保留 REJECTED 审计事件；重试相同请求仍返回原拒绝，不重新计算并补成交。

## 领域与数据契约

- 复用 `AssetId / UniverseSnapshot / Signal / TargetPortfolio / OrderProposal / TradingSession`。
- `CADState` 与旧 USD `PortfolioState` 分开；禁止把 CAD 数值误当 USD。CAD/USD 每币种独立非负现金。
- `Quote` 是原始可交易价格，不接受 adjusted。必须带 observed_at、available_at、source、synthetic、
  kind、tradable 和 volume；成交数量不能大于该报价的声明成交量。
- `Sector` 有 effective_at 和 available_at；持仓/目标缺失或晚可得行业时阻断，不默认为零行业风险。
- `SignalBundle` 包装已有信号和统一 Universe；明确来源、synthetic / paper_observed。
  `descriptive_only=True` 拒绝进入订单；Phase 3 回归没有隐式转换器。
- `bundle_from_ml_predictions(...)` 接受 Phase 4 审计记录、已选定 model 与明确 data_kind。
  校验 fit_at/available_at，仅取分数，不读取标签或按测试指标选模型。分数不称校准概率。
- native Paper JSON 是 `{"schema_version":5,"payload":...}`；闭集类型标签 `type/fields`，
  Decimal、UTC datetime、date、tuple、dict 分别用显式单键标签。拒绝未知类型/字段，不用 pickle。
  `paper sample` 生成完整可编辑示例；Python 服务可直接传强类型对象。

历史 FX CSV 固定列：`observed_at,available_at,cad_per_usd,source,synthetic`。
`load_fx_csv(Path(...))` 导入，`FXBook.at(t)` 只从 observation 和 availability 均≤t 的记录中，
选择最新 observation、再选当时最新可用 vintage。观察时点相同且 availability 相同的冲突记录拒绝。
不会用未来值回填缺失，不会把本次下载时间伪造成历史发布时间。超龄/缺失 FX 阻断 USD 现金或资产估值/交易。
包内 `resources/paper_fx.csv` 是两行明确 synthetic 历史样例，可通过导入服务使用；没有在线 FX 下载器。
报价与 FX 的默认最大年龄7天，可配置；这不保证报价具有真实流动性或来源已获 PIT 认证。

## 数学与记账

所有计算固定 Decimal 50位上下文，隔离调用方精度。现金/原始成交报价为整分，费用向上舍入到分。
以 `r = CAD per USD`，每个资产与现金币种的换算因子是 CAD=1、USD=r：

`NAV_CAD = cash_CAD + cash_USD*r + Σ(quantity * raw_mark_local * currency_rate)`。

累计手续费、滑点与换汇成本只是披露，**不能再从 NAV 扣除**。成交后在同一原始市场标价下：

`NAV_before - NAV_after = commission_CAD + adverse_slippage_CAD + FX_fee_CAD + FX_rounding_CAD`。

买价按不利滑点上舍入，卖价下舍入；佣金 = ceil_cent(fixed_fee + notional*commission_bps/10000)，
在资产本币扣除。USD 已有现金优先使用；不足时仅购买缺少的 USD 分：

`CAD_principal = ceil_cent(USD_shortfall*r)`；`FX_fee = ceil_cent(CAD_principal*fx_fee_bps/10000)`。

CAD 扣 principal+fee、USD 增 shortfall；多扣不足1分的本金差额单独记 rounding。
卖出 USD 证券的净款保留 USD，不偷偷兑换第二次。显式 `CONVERT(source="USD")` 才卖 USD：
CAD 收 `floor_cent(USD_amount*r)-ceil_cent(floor_cent(USD_amount*r)*fee_bps/10000)`。
`CONVERT(source="CAD", amount=x)` 的 x 明确表示**要买到的 USD 数量**，不是 CAD 支出预算。
CAD 资产买入需要 CAD 现金；不会自动卖 USD 现金弥补 CAD 不足，需先显式换汇。

持仓保存整股数量、本币成本与 CAD 成本。买入成本包括一次佣金及相关 FX 成本；
部分卖出按平均成本分摊，全卖取剩余全部成本，避免残差；不是税务 ACB 计算器。
每个持仓报告 local_pnl、cad_pnl、local_cost_return、cad_cost_return，以及恒等分解：

`cad_pnl = local_pnl*current_rate + fx_translation_cad`。

translation 项也包含成本基准的币种/转换费用差异，不能称为纯汇率 alpha。
成本收益率不是按外部现金流调整的组合时间加权收益率；本阶段不伪造 Sharpe/年化策略表现。
净入金单独计 `net_contributions_cad`；USD 入金按流入当时已知 FX 记录，入金不当投资盈利。

`ACTION` 仅实现简单 SPLIT 和 DIVIDEND：拆股不改总成本，分红只增加现金一次。
操作必须在 effective_at、严格晚于账户前一经济状态、且信息已可得，先于同刻或以后交易；
实际支付/除权多日期、税、合并、现金替代零股和追溯修正不支持，显式拒绝。
同一 effective_at 的多项行动需要未来权益快照/批处理设计，本阶段保守拒绝第二项，不人为错开真实事件时间。
调用方必须保证原始价格/公司行为/时点一致；系统无法从伪造的自洽元数据推断遗漏的真实公司行为。

## 风险、时间和执行

Top-K 排名使用既有等权规则；按单票/行业/持仓数截断，行业内均分可用上限；不迭代优化。
显式 TargetPortfolio 也必须通过同样限制。按决策 NAV 与已知 CAD 价格向下取整计算目标股数，
先卖后买，按费用后 NAV 对买入量做确定性二分缩减；最小成交额/单笔/总换手/股数均受限。
无法修复的继承风险（例如受交易上限限制无法减仓）显式报不可行。

决策数据必须满足 available_at≤decision_at；session 清单必须有前一收盘和后一开盘、无重叠，
选择清单中下一 session。执行时 decision_at<execution_at，且必须跨日期、恰好是计划开盘；
持仓和订单都需要该时点原始 open 报价，available_at≤execution_at。
开盘价与参考价偏离超过上限、现金/FX/行业缺失、成本后风险超限时整批拒绝。
清单本身仍由调用方负责，不是权威交易所日历认证；不支持盘中或跨市场不同时开盘的批次。
单笔及换手额以本批次执行前 NAV 与原始报价计，不含费用；费用后仓位/现金风险再次检查。
估值允许报告价格漂移产生的超限，不会宣称仓位上限持续成立，也不会偷偷自动交易。

`run_cad_history(initial_state, tuple[CADHistoryStep,...])` 复用同一个 planner/simulate_plan/value_portfolio，
但只允许 synthetic 的信号/行情/FX，不写 Paper 数据库。真实 paper_observed 仅表示正向虚拟输入，
它的时点声明需来源证据支持；不能据此在历史接口宣称可信 PIT/OOS。旧 USD Backtesting Engine 保持兼容。

## 持久性与恢复

一个本地 SQLite 文件对应一个 CAD 虚拟账户，schema v1。`BEGIN IMMEDIATE` 将幂等检查、原输入、
事件追加、结果指纹和 ledger_head 更新放入同一事务；synchronous=FULL、默认 rollback journal。
重复完全一致的请求返回当前重放状态，不再次产生经济事件；相同 ID 改输入明确报碰撞。
执行失败保留一条 REJECTED 事件，经济状态不变。无待审订单资金预留，账户变化会令旧计划过时。

重启逐事件从初始资本重建现金/持仓/成本/流水/订单/估值/信号/最后时间；
检查 SQLite 结构、连续序号、输入与前驱 hash、结果 hash 和独立末端记录。
算法/数值语义变化导致结果不一致时停止，要求未来显式版本迁移，不悄悄重写历史 Fill。
插入后提交前中断，SQLite 回滚整笔事务；提交后响应丢失，再次相同请求不会重扣。
这是本地一致性检查，不是防有权限者同时重写整个账本的认证签名，也不能识别人为替换成完整旧备份。

`paper apply --db ... --event-id <稳定唯一ID> --input <native.json>` 支持 CASH、CONVERT、ACTION、VALUE。
事件必须有 kind/at 和严格对应字段。现金流/换汇/公司行为可通过同一事件ID安全重试；VALUE 持久化 NAV 历史。
入出金只检查现金不透支；若出金引起集中度漂移，需新市场快照检查并重新规划。
报告包含原始事件、现金/持仓/计划、trades.csv、nav.csv、HTML、provenance/逐文件hash及最后 run.json。
文件和本地账户都被 Git 忽略；备份请在写入停止后保存完整数据库，勿删除运行中的 journal。

实现根据 [SQLite atomic commit](https://www.sqlite.org/atomiccommit.html)、
[Python 3.12 sqlite3](https://docs.python.org/3.12/library/sqlite3.html) 和
[Decimal](https://docs.python.org/3.12/library/decimal.html) 官方资料核对；
磁盘/文件系统可靠性仍由本机环境承担。本阶段没有网络盘/跨主机并发或长历史性能认证。
