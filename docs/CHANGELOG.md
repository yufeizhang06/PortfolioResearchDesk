# Changelog

## 0.7.0 — Phase 6 (2026-10-28, final development acceptance)

- Add offline doctor, exclusive workspace templates and a unified synthetic
  universe/research/USD backtest/CAD paper lifecycle with local HTML index.
- Optional independent factor/ML workflows; development-selected ML predictions
  produce a separate unexecuted pending CAD proposal. No new model or optimizer.
- Add strict readable Paper snapshots, explicit targets, compact plan/summary,
  valuation, cash-flow and FX commands; keep native inputs and old commands.
- Preserve hash-bound manual review, atomic simulation, restart and idempotency;
  flag recorded NAV stale after economic changes, including same-time events.
- Verify confined immutable report hashes; preserve incomplete-run evidence.
- English README, user guide, Architecture & Code Walkthrough, contribution and
  release-readiness documentation; defer Streamlit without new runtime dependencies.
- Use user-confirmed MIT for original code/fixtures; package third-party notices and provide
  an installed metadata inventory without claiming data redistribution clearance.
- Extend Ubuntu/Windows CI configuration and both-wheel isolated installation
  checks. The user authorized safe private synchronization; exact-SHA remote CI
  and Git results are recorded in PHASE_6_REPORT. No visibility/release action.
- Retain real PIT, survivorship, corporate-action/calendar and ML OOS limitations.
  Actual test counts, numerical checks and independent review: PHASE_6_REPORT.
- Final local rerun: 689 tests; all 11 user-workflow items PASS in their synthetic
  scopes. Unsupported real PIT/OOS, automatic real-universe history, Dashboard and
  brokers remain explicit. Functional e49d797 safely merged/main and normally
  pushed with the Phase 6 branch. Actual run 40793091056 passed Ubuntu/Windows
  (689 tests each), all quality/CLI/build/install gates; workflow_dispatch.
- No formal v1.0.0 Release or public visibility; stop for author experience acceptance.


## 0.6.0 — Phase 5（2026-10-28，已验收并同步Private）

- 新增CAD/USD虚拟账户、历史FX可得时间/版本及native CSV、换汇费/舍入、CAD现金/持仓成本/NAV。
- 可配置持仓数、单票/行业/现金、单笔金额/股数/最小额/总换手、价格偏离和数据年龄限制。
- Top-K保守等权、显式目标、整股缩单、先卖后买；复用旧Signal/Universe/Target/Order契约。
- 人工审核绑定plan hash，下一显式session原始open整批模拟，现金不足/数据缺失/风险超限不产生部分成交。
- SQLite原子事件、输入/结果指纹、hash链/末端记录、重启重放、并发幂等、防重复成交和计费。
- 入出金、显式换汇、基础拆股/分红、估值历史；公司行为时序与不支持场景显式阻断。
- CLI paper init/sample/propose/review/simulate/status/expire/apply/export/demo，独立严格配置、JSON/CSV/HTML报告。
- CAD synthetic history复用同planner/模拟计算；ML审计记录适配器不读标签，真实历史PIT与描述性因子边界保留。
- 独立初审发现的高固定费卖单、混源、同刻公司行为、估值时钟及输入异常问题均已修复并保留回归。
- 完整测试、独立复核、构建与安装的最终实测结果见PHASE_5_REPORT；不挪用Phase4远端CI。
- 版本和uv.lock由uv同步至0.6.0；既有第三方包版本不变，不进入Phase6或创建Release。
- 最终核实46生产源码/13独立证据一致；新增研究→Paper重估→新进程完整恢复联合回归，全量609 passed。
- 用户已授权正式Commit/快进main/普通Private Push/真实Ubuntu与Windows CI；准确SHA及实测结果见PHASE_5_REPORT。
- 功能提交8904e11已快进main并普通原子Push main/Phase5；真实CI40759391233精确该SHA双平台success。
- Ubuntu3.12.15/Windows3.12.10各609测试、Ruff/CLI/构建/sdist重建/双wheel源码外安装通过；本次workflow_dispatch。

## 0.5.0 — Phase 4（2026-10-27，合成USD软件验收）

- 新增可追溯价格/波动/流动性/相对收益特征、next-open 未来收益标签及可得/已知时间契约。
- 全局日期 expanding/rolling、整日期 purge、gap、安全 embargo、内层 TimeSeriesSplit 调参。
- prior、Logistic、Lasso 连续回归、Random Forest、CPU XGBoost；训练内 Pipeline 与小网格。
- 完整分类指标/覆盖、开发冻结 winner/参数、独立 Holdout 及每折审计；不择优隐藏结果。
- 可选信号入口复用旧回测引擎，与 Cash/Buy-Hold/Equal-weight/Momentum 公平合成净值及成本比较。
- prd ml run / config validate --kind ml、不可覆盖 JSON/CSV/HTML、快照/账本/代码依赖指纹。
- ml extra 与 uv.lock 正式解析，CI/双 wheel 源码外验证扩展；真实双平台CI在05d1900通过。
- 合成 USD 实现验证；无真实 PIT/OOS 认证，不用 Phase 3 事后因子，不进入 Phase 5。
- 开发期419 passed；最终补测后425 passed（保留原330，新增95），Ruff/锁/构建/sdist重建/双wheel干净安装通过。
- 独立审查无可操作P1/P2/P3发现，144组合/3024 folds/906990训练行及五模型未来扰动验证通过。
- 最终验收核实生产36文件与原审查SHA一致；补6项外层标签/Holdout特征与标签隔离测试，全量425 passed。
- 用户授权正式Commit/快进合并/Private Push和双平台真实CI检查；实际Git/CI结果按验收报告后续实测记录。
- 保留Holdout治理限制：程序冻结仅支持合成验证，不宣称真实研究未触碰测试集或校准上涨概率。
- 正式功能提交05d1900已快进合并main、普通原子Push main/Phase4；仓库仍Private，历史分支保留。
- 真实CI40602662692（准确SHA05d1900）Ubuntu/Windows各425测试与全部安装检查通过，使用workflow_dispatch。

## 0.4.0 — Phase 3（2026-10-27，已通过用户验收）

- 独立审查 R1–R5 全部 PASS，用户正式验收；范围仅事后描述性因子研究，不代表 PIT/OOS 交易策略通过。
- 本阶段已正式 Commit、快进合并 main 并普通 Push 到原 Private 仓库；保留 Phase 2/3 分支和完整历史。
- CI修复提交139d17f的真实Ubuntu/Windows CI均通过：各330测试、Ruff、CLI、构建、sdist重建与独立安装；
  运行40597881595为workflow_dispatch，不宣称已验证Push自动触发链路。
- 首次真实CI发现冷缓存的requirements离线解析缺少registry元数据；安装验证改为直接按锁文件同步到隔离venv，
  保留wheel并核对其来源，全部Phase0–3检查保留；不修改业务、测试或锁定依赖。
- R5：共享日线质量检查核对已知事件与交易所本地日标签；按来源契约区分显式时间与次日本地零点上界。
  时间矛盾隔离且因子研究退出 2；缺少事件/来源/时区证据时明确显示仅描述性且不适用严格历史流程。
  不以晚下载为错误，不虚构历史发布时间；新增 32 个案例，全量 330 passed，R1–R4 及原测试保持。
- 月频按完整名义月份网格滚动，补齐双边缺失和区间边缘月份；不扩大窗口取旧数据。
- 月频清单与已知报价冲突明确拒绝；拒绝将 provider_adjusted Close 宣称为纯价格收益。
- 因子百分数用精确十进制移位转换；缓存键升级 v2，保留但隔离旧精度相关缓存。
- 新增 28 个回归/边界案例，四个主反例先失败后通过；全量 298 测试通过。
  OLS 数学函数和原 19 个测试文件保持不变，20 组独立参考复核通过。

- US French FF3/Mom 日频/月频 ZIP/CSV、单位和 RF 契约、来源/读取快照及不可变缓存。
- 股票简单收益/同期超额收益、显式月末 session 端点、共同有效样本与可审计剔除原因。
- FF3/Carhart FF4 OLS 完整推断、经典/HC3 SE、条件数/VIF、残差诊断、AIC/BIC 同样本比较。
- 每个尾随窗口独立拟合，保存失败窗口，不因缺失延长窗口，不允许未来观察影响过去暴露。
- prd research run、Phase 3 配置、JSON/CSV/HTML/SVG/PNG、输入和代码/依赖指纹。
- 正交已知答案与误差公式测试、未来扰动、错位/缺失/奇异/零残差/依赖及导出异常测试。
- yfinance 元数据兼容 Mapping，保留身份验证并避免触发无关的惰性请求。
- factors 可选依赖由 uv 锁定，扩展 CI/源码外独立安装验证；未执行 Phase 3 远端 CI。
- 保留 Phase 0–2；不加入 ML、真实回测、FX、持久账户，不自动 Commit 或 Push。

## 0.3.0 — Phase 2（2026-10-27）

- 用户验收后完成英文 GitHub README、首次 Private 上传；保留 main 与 Phase 2 分支及原始历史。
- 修复全新 checkout 下 pytest 固定临时父目录缺失；没有修改业务逻辑或删减测试。
- Ubuntu/Windows 真实 GitHub Actions 均 208 passed，Lint、CLI、构建与独立安装通过。
- Yahoo/yfinance 日线与 native CSV/Parquet Adapter；来源、时间、复权、公司行为字段显式保留。
- SQLite 索引、不可变校验快照、real/synthetic 隔离、TTL、离线命中、显式刷新与过期选择。
- 有界重试、限流停止、身份与元数据验证、缺失/重复/异常隔离及逐资产失败记录。
- 自选列表导入/导出/更新/去重；Nasdaq 官方当前目录；流动性/动量/波动率组合筛选。
- 统一 UniverseSnapshot、current/user_static/PIT 标签、历史 PIT 阻断、可得时点及未来扰动测试。
- 统一研究运行报告、CSV 元数据配对、配置/数据/代码/依赖指纹和不可覆盖运行目录。
- 保留 Phase 0–1 行为；可选 data 依赖锁定；扩展离线 CI 和独立安装验证。
- 本地 208 测试通过，真实下载与缓存/Parquet 回放已实际运行；远程验证详见开发日志。
- 真实数据仅限描述性研究；历史指数/退市、真实回测、因子及 ML 不在本次交付范围。

## 0.2.0 — Phase 1（2026-10-27）

- 自选 user_static 股票池、规范化 raw USD 合成行情、明确 session schedule。
- 过去窗口动量、确定性 Top-K 等权、现金及单票约束、整股订单请求。
- 下一 session 开盘、先卖后买、费用/滑点/资金不足缩单、持仓和净值核算。
- 不可覆盖的运行目录、输入/版本指纹、JSON/CSV/HTML 及现金基准。
- 手算回归、未来扰动、缺失/异常时序、执行和报告异常测试。
- 保留 Phase 0 CLI；扩展 CI 和 sdist/wheel 独立安装验证。
- 真实数据依然未接入；用户确认后在 Phase 2 开始，远程 CI 状态单独记录。

## 0.1.0 — Phase 0（2026-10-27）

- 原样收录用户提供的项目计划书；SHA-256 与下载版相同，未修改未来阶段清单。
- 添加 src 可安装包、CLI 帮助、版本、严格 TOML 配置和内置合成数据摘要。
- 添加 uv 锁定环境、pytest、Ruff、离线构建和独立安装验证、GitHub Actions。
- 添加 README、AGENTS.md、架构决策及真实验收记录。
- 未实现 Phase 1–6，下一阶段须用户确认。
