# Phase 5 验收报告 — Portfolio Risk, CAD/FX & Paper Trading

日期：2026-10-28（America/Toronto）；开发版0.6.0。
分支：`codex/phase-5-cad-paper`；稳定基线：`0e4ca9677ed2e53dd2641b0f49157de88030aaa8`。
本地开发及独立修复复验已完成；用户已原则批准最终验收、正式Commit、安全合并main、Private Push与真实CI。
下文608测试/未提交/未运行CI是此前本地验收记录；本轮最终收尾与实际Git/CI结果见末节。
**仅合成软件验收，不执行真实订单，不创建Release或进入Phase6。**

## 开始状态核实

- 已完整读取AGENTS、PROJECT_PLAN、README、DEVELOPMENT_LOG、Phase4验收和实际domain/组合/执行/ML接口。
- 初始工作区干净，实际fetch确认main/origin/main同为0e4ca96，从main创建独立Phase5分支。
- 原Phase2、Phase3、Phase4分支和历史保留；原始计划书不改。
- 基线实际重跑425 passed in35.17s。未将旧CI当成本阶段CI，未创建远端工作流运行。
- Python3.12.14、uv0.13.6，PATH不含工具；使用work/bin/uv.exe和work/phase4-venv。
- 零新增第三方依赖，使用标准库Decimal/SQLite；uv正式解析项目版本0.5→0.6，原有锁定包版本不变。

## 已实现及验收映射

| 要求 | 实际实现 |
|---|---|
| Portfolio Risk Constraints / FR-10 | 持仓数、单票、行业、现金缓冲、最小/最大单笔额、股数、批次换手、价格偏离、数据年龄；目标和费用后实际持仓都检查 |
| Multi-Currency / FR-14 | CAD/USD资产与现金，历史FX/vintage/available_at、本币费用、自动按需USD资金兑换及显式双向兑换 |
| CAD Ledger | 本币/基础币成本、现金、成交、佣金、FX费与舍入、滑点、已实现损益、分红、净入金、CAD NAV及本地/CAD成本收益归因 |
| Paper Trading / FR-13 | 本地SQLite账户，待审/已审/模拟/拒绝/过期计划、订单、成交、信号、现金/仓位/估值历史与导出 |
| Rebalancing Planner | 研究信号或显式目标+当前持仓+资金+风险，确定性Top-K/等权/保守行业截断，整数股、费用后缩单、清晰原因和成本 |
| State Recovery | 初始资本重放、原子事务、并发唯一请求、相同ID同输入不重复成交/扣费、变输入碰撞、逐事件结果hash与链/末端检测 |
| 原有接口兼容 | Signal/UniverseSnapshot/TargetPortfolio/OrderProposal复用；旧USD接口保留，Factor边界不变，Phase4预测记录可显式适配 |
| 模式/时间 | historical CAD仅synthetic；Paper显式来源；synthetic禁止混real执行；下一session、行情/FX/行业/信号可得性、错误时间拒绝 |
| CLI / FR-15/17 | 严格paper配置及薄CLI，native输入、JSON stdout/诊断stderr/错误退出2，JSON/CSV/HTML、provenance与最后完成标记 |

主要新增：fx、portfolio_risk、paper_domain、rebalancing、paper_execution、paper_store、paper_config、
paper_cli、paper_reporting、paper_sample，包内/configs样例与五个测试文件。
旧domain仅加强UTC输入验型，portfolio提取原等权函数，cli注册新命令；旧回测/ML数学算法未改。
详细设计、字段、计算、手动审核流程见 [PAPER_TRADING.md](PAPER_TRADING.md)。

## 会计与时间不变量

- `NAV_CAD = CAD现金 + USD现金*r + Σ整股数量*原始本币价格*货币汇率`。
- 每币种现金≥0；无卖空/杠杆；费用/FX损耗已在现金体现，累计披露值不再从NAV扣一次。
- 同一时点标价的交易前后NAV差精确等于佣金CAD+不利滑点CAD+换汇费CAD+本金舍入损耗CAD。
- 持仓本币/CAD平均成本按卖出量分摊，全卖移除全部剩余成本；分红只记现金，拆股不改总成本。
- 决策所用输入available_at≤decision_at；开盘模拟decision_at<execution_at、跨日期、精确匹配计划下一session。
- 成交重新检查当时开盘、FX、行业、实际成本和风险；跳空导致计划失效时整批REJECTED，无部分扣款。
- 计划绑定原账户state hash和完整plan hash；修改账户后旧计划不可执行。错执行时间不写事件或消耗幂等键。
- SQLite一事务记录请求/输入/结果hash/末端；进程在插入后提交前退出，恢复保持旧账；提交后重试保持单笔经济结果。

## 独立数值对照

正式手算测试从1,000 CAD开始，USD/CAD=1.25、每单固定佣金1本币、FX费100bps、零滑点：

| 步骤 | 独立结果 |
|---|---|
| 买32股USD10 | 需321 USD；CAD本金401.25，FX费4.02，剩CAD594.73 |
| 买15股CAD20 | 扣301 CAD，剩CAD293.73、USD0 |
| 同价估值 | NAV993.73 = 1000 − 佣金CAD2.25 − FX费4.02 |
| USD资产涨至11、CAD资产降至19、FX变1.30 | NAV = 293.73 + 32×11×1.30 + 15×19 = 1036.33 |

使用Fraction独立oracle核对成交/佣金/FX本金与费用的向上舍入、现金和NAV；不调用生产费用函数当期望值。
部分卖出成本、USD原币现金使用无二次FX费、双向兑换损耗、外部入金、拆股/除息后NAV守恒另有测试。
这是人工构造数值验证，不是市场收益或真实策略证据。

默认3,000 CAD演示实际产生3笔成交：CAD资产29股、USD资产44/17股，终现金1,238.08 CAD、USD0，
开盘估值NAV2,994.48 CAD；佣金1.2840 CAD、FX成本（含舍入）2.3640 CAD、滑点1.8720 CAD，
合计5.5200 CAD，恰与NAV损耗一致。全部风险约束通过，无透支。
本地报告与账本留在outputs；不是受检市场策略，也不上传账户文件。

## 测试、复现与实际结果

本机PowerShell任务环境（非全局配置）：

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) 'work/uv-cache-phase3'
$env:UV_PROJECT_ENVIRONMENT = 'work/phase4-venv'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
```

下面uv在本机替换为work/bin/uv.exe；README保持通用命令。

```text
uv sync --locked --extra data --extra factors --extra ml --offline
uv lock --check --offline
uv run --locked --offline pytest -p pytest_socket -q --basetemp work/phase5-acceptance-tests -p no:cacheprovider
uv run --locked --offline ruff check .
uv run --locked --offline ruff format --check .
uv run --locked --offline prd --help
uv run --locked --offline prd --version
uv run --locked --offline prd config validate --kind paper --config configs/example_paper.toml
uv run --locked --offline prd paper demo --db outputs/paper/phase5-validation.sqlite3 --run-id phase5-validation
uv run --locked --offline prd paper status --db outputs/paper/phase5-validation.sqlite3
uv build --offline --no-build-isolation --out-dir dist/phase5
uv run --locked --offline python scripts/verify_distribution.py dist/phase5 --uv <uv绝对路径> --with-factors --with-ml
```

已有demo数据库/Run ID不覆盖；重新演示须换新路径/ID，幂等重试使用相同simulate请求。

- 基线425；初版全量593 passed in40.78s；初审修复后603 passed in32.07s。
- 最新小范围store/workflow62 passed in1.66s，额外5例覆盖未哈希字段输入/旧表结构；最终全量结果见末节。
- 原425项测试文件保留；pytest-socket禁止测试网络，固定样例/时间/参数，不依赖API Key或动态行情。
- 金融计算、非法金额/价格/成本/币种、现金不足、缺FX/行业、同日/晚可得/错时点、未来FX扰动、
  整数股、目标不可行、状态恢复、并发重复、损坏/截断/结果漂移、report不可覆盖/I/O故障均有回归。
- 进程中断测试在子进程INSERT后COMMIT前os._exit(17)，真实重新打开账本检查，无重复经济事件。
- 完整手动CLI lifecycle测试含propose保持待审、无审核不成交、plan hash审核、重启、重复simulate与不可覆盖导出。
- CI配置和独立安装脚本已扩展到Phase5；**本阶段没有远端CI运行，不声称Ubuntu通过**。

## 独立 Code Review 与修复记录

用户要求的独立代理采用只读审查，独立材料保存在work/phase5-independent-review/。
审查可写自己的probe/报告，不修改生产或正式测试。

初审找到并已修复、各有正式回归：

1. 高固定费卖单：小卖量不足支付费用不能作为更大卖量不合法的二分上界；改最大可交易量直接验证。
2. synthetic Paper执行混入真实报价/FX：现对所有synthetic模式阻断混源。
3. 同刻成交后补记公司行为会按新买股份派息：现要求前经济状态严格早于行动生效；同effective多行动保守拒绝。
4. CAD history估值后状态时钟仍停开盘：现推进至valuation_at，阻断后续倒退。
5. native字符串金额/数字plan ID、未哈希currency/source/asset/kind：均先验型并返回预期错误2，无traceback。
6. 损坏/旧五列表结构用SELECT*解包报ValueError：显式版本列查询，转为预期数据库错误。

另主动补强：逐事件结果hash/同事务ledger_head防计算语义漂移及尾行截断；错误执行时间不污染last_at。
保留初始反例和初审结果，不把修复前状态重写为通过。最终独立复核与源码hash一致性见末节。

## 限制、差异与下一阶段依赖

- 本阶段验证范围为合成USD/CAD软件与本地Paper流程；没有真实市场PIT/OOS或策略盈利认证。
- 真实行情/PIT/成员/退市/权威日历/授权缺口保持，CAD真实交易Adapter不在本阶段；FX仅native历史CSV，没有在线来源下载。
- Paper接受明确forward来源及可得时间的手工数据，不等于历史认证；自洽元数据造假无法由程序单独识别。
- 公司行为只支持明确定义的简单split/dividend；无权益登记/支付多时点、税、复杂重组、追溯修正或同刻行动批处理。
- 同一批次需同一明确开盘时点，无跨市场不同开盘调度、盘中、部分撮合、资金预留、自动broker或真实订单。
- 成本为配置情景参数；volume为调用方声明，不证明真实成交可得。价格漂移只报告风险，不自动交易。
- 本地单账户SQLite逐事件完整重放，没有跨主机/网络盘、海量事件性能、外部签名或灾难恢复认证。
- 成本收益归因不是组合时间加权收益/税务ACB；无复杂优化、波动协方差/VaR/校准概率或收益承诺。
- 多项目标受限时保留现金或显式不可行，不强行冒险；USD收益留USD、CAD不足要先显式兑换。
- Phase6仍需用户单独授权；本轮不开始Dashboard/产品化/Release。真实数据链路仍需来源/PIT/日历/公司行为证据。

## 最终验收记录

| 实际执行项 | 结果 |
|---|---|
| 全量pytest | **608 passed in34.69s**；原425保留，新增183；禁socket |
| Ruff lint / format | All checks passed；93 files already formatted |
| uv sync --locked / lock --check --offline | 通过；58个锁记录，原第三方包版本不变 |
| CLI / 配置 / 3,000 CAD demo / 重启status | 全部通过；JSON状态重启前后逐项一致 |
| wheel + sdist + sdist重建wheel | 实际构建成功，位于dist/phase5 |
| 两个wheel独立安装 | 各自干净venv，源码外Phase0–5、资源、Factor/五ML模型及Paper持久恢复通过 |
| 独立Code Review复验 | 214 passed in1.82s（183新+31旧）；1,000 Fraction精确oracle通过 |
| 独立并发/损坏/漂移检查 | 8线程24请求仅4事件3fills；尾部截断/结果漂移/错误时钟/旧schema均拒绝 |
| 主代理最终审计 | 46生产源码、13审查材料SHA一致；32候选文件敏感模式未检出；包无work/outputs/venv/真实数据 |
| Git边界 | 分支codex/phase-5-cad-paper，HEAD/main/origin/main均0e4ca96，无暂存或提交 |
| Phase5远端CI | **未运行**；本轮未Commit/Push，不挪用Phase4 Ubuntu/Windows通过结果；macOS亦未实测 |

独立审查结论：**初始发现修复并复验后，冻结源码没有未解决、可操作的P1/P2/P3发现**。
只适用于合成CAD/USD软件和本地虚拟账户，不能扩大为真实市场或完整公司行为认证。
主代理已读取独立报告、数值probe和结果，逐项比对review-manifest、当前46文件及13证据hash，未再改生产。

实际本地证据：

- `work/phase5-closeout/final-full-tests.log`、`build.log`、`distribution.log`；
  安装日志最终明确 `PASS: sdist rebuild, both wheels, clean install and CLI/resources on 3.12.14`。
- `work/phase5-closeout/paper-demo.json`、`paper-recovered.json`、`audit.json`。
- `outputs/paper/phase5-validation.sqlite3`、`outputs/paper-reports/phase5-validation/`，仅本地且Git忽略。
- `work/phase5-independent-review/REVIEW.md`、`review-manifest.json`、`initial-results.json`、
  `verified-results.json`、`numeric-final-results.json`、`persistence_results.json`和输入边界结果；初始失败证据保留。

独立报告SHA-256：`45e1c7f486e9b65f212a5d8dd68472a672821b0652666e5f31cbf263039ae116`。
原始计划SHA-256仍为`1f208c70b41aeaecfac45f1e38bcd2d3ff674f6eb1868352b45fd9eb40f752bb`。

构建保留uv关于缓存位于源码树内的提醒，但归档清单审计确认未打入缓存/账户/输出；
隔离安装VIRTUAL_ENV不匹配提醒说明明确指定了新venv，实际wheel来源和sys.prefix断言通过，未用editable掩盖缺文件。
最终文档补记后再次构建，核对归档生产源码与已独立安装/审查的46文件逐项一致；不为仅文档变化重复模型实验。

上述为最初本地验收快照，未提交/CI未运行状态保留作历史记录。本轮用户已另行授权Git与CI收尾。

## 最终验收与 Private GitHub 同步（2026-10-28，用户授权）

### 证据和当前文件核实

- 实际fetch确认main/origin/main仍0e4ca96；仓库yufeizhang06/PortfolioResearchDesk仍PRIVATE、默认main。
- 独立报告、review-manifest及13份证据SHA全部一致；46生产Python文件与冻结审查快照逐项一致。
- 无未解决可操作P1/P2/P3，已有数值/会计/FX/风险/原子性/重启/重复订单和模式隔离证据充分，不重做完整独立审查。
- 仅补1项跨研究→计划→成交→价格/FX重估→新进程完整恢复→导出的联合回归；生产算法未改。
- 原计划、原425测试、第三方锁版本保留；新合计609测试（425旧+183原Phase5+1收尾联合回归）。

### 实际3,000 CAD全流程演示

复用momentum_signals、SignalBundle、现有CAD planner/execution和Paper CLI，无新生产实现。
两个合成历史收盘生成1-session动量，决策2026-01-05 21:02 UTC；按已知价格/FX和约束生成目标。
三资产各20%、现金40%；固定整数股订单默认PENDING_REVIEW。
依据本次用户对合成验收演示的授权，脚本显式记录审核与plan hash（21:03 UTC），下一session开盘才模拟成交。
此脚本审核只用于软件验收，不冒称真实人工投资决策或PIT/OOS表现。

| 环节 | 实际计算/检查 |
|---|---|
| 初始账户 | 3,000 CAD、USD0，无持仓 |
| 合成研究 | SYN_US_A：9.50→10；SYN_CA_B：19→20；SYN_US_C：24→25，旧momentum_signals计算分数 |
| 目标/订单 | 各20%+现金40%；CAD_B买29股、USD_A买44股、USD_C买17股 |
| 2026-01-06 14:30 UTC模拟开盘 | USD/CAD1.36；CAD现金1238.08、USD0；NAV2994.48 CAD，无风险违规 |
| 成本对账 | 佣金1.2840 + FX费/舍入2.3640 + 滑点1.8720 = 5.5200 CAD，恰等于初始NAV损耗 |
| 同请求再执行 | 返回同结果，事件数/股数/现金/累计费用不变 |
| 21:00 UTC价格及FX变化 | USD_A10.05、CAD_B20.05、USD_C25.10；USD/CAD1.30，来源均synthetic且已可得 |
| 重估 | NAV2949.10 = 1238.08 + 29×20.05 + (44×10.05+17×25.10)×1.30，无风险违规 |
| 变化独立分解 | 本地价格影响+6.754 CAD；FX影响−52.134 CAD；总变化−45.38 CAD，不再扣费 |
| 关闭/恢复 | 全部SQLite连接关闭，另起Python进程重放；完整账户含plan/fill/现金/持仓/估值/hash与关停前完全一致 |
| 导出 | account.json、events.json、trades.csv、nav.csv、report.html、run.json；共5事件、3成交、2次估值 |

本轮独立Fraction计算再次核对重估NAV。价格/FX变化只追加VALUE，不产生现金变动或额外成本。
原始命令JSON和完整恢复前后快照在work/phase5-finalization/scenario/，summary.json为汇总。
实际数据库outputs/phase5-final-acceptance/account.sqlite3，报告outputs/phase5-final-acceptance/reports/complete/，全部仅留本地。
复现脚本work/phase5-finalization/scenario.py；采用不可覆盖目录，再跑须新路径。正式联合回归可反复在pytest临时目录执行。

### 本轮质量门槛与Git/CI

- 锁定离线sync/lock通过；全量 **609 passed in32.81s**，socket禁用；Ruff lint与93文件format通过。
- wheel/sdist构建、sdist离线重建及两个wheel各自干净venv源码外Phase0–5安装/资源/恢复均实际通过；
  产物dist/phase5-finalization，日志work/phase5-finalization/build.log与distribution.log。
- 审核32候选文件，敏感模式未检出；10类.gitignore样例通过；归档不含work/outputs/venv/账户/真实数据。
  46生产源码与审查hash一致，第三方锁记录不变；审计work/phase5-finalization/audit.json。
- 计划正式消息：`feat: implement CAD portfolio accounting and paper trading`。
- 仅普通提交/快进合并/Push至原Private仓库，保留Phase2/3/4/5和全部历史；准确SHA/远端CI将在成功后记录。
- Phase6只列后续目标：产品化文档、复现与数据授权检查、可选Dashboard、最终验收；没有开始或创建Release。
