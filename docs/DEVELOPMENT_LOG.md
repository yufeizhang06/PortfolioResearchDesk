# Development Log

## 2026-10-28 — Phase6最终本地验收通过，准备授权Git同步

- 生产/测试/配置/安装代码与独立审查快照一致，只有MIT与收尾状态文档改变，无未解决阻塞。
- 本轮689 passed in43.20s、Ruff lint/format、锁/sync通过；不改旧测试、核心算法或依赖版本。
- 17次实际CLI子进程：自选CSV导入/选择→3资产筛选保留A/B排除C→完整研究/因子/5模型35fold→USD回测与CAD人工审核账户。
- 独立账户3000CAD→未审核拒绝→确切hash人工批准→2模拟成交→NAV2971.1700；新进程恢复与重复执行完全一致，5事件不重复扣费。
- 完整workflow63文件验证，Factor Mom系数0.4999999999999997；USD合成10fills与CAD账户分开解释，不夸大真实策略表现。
- wheel/sdist、sdist离线重建、双wheel源码外干净安装(base/factors/ml/完整workflow)全部PASS；生成报告与账户仅保留work/。
- 158候选文件敏感模式/禁止文件/文档链接检查通过，MIT正文/2026 Yufei Zhang/打包元数据一致；57依赖无安装版本不符。
- 原计划hash不变。下一步按授权正式Commit、安全合并main及普通Private Push；远端CI以准确SHA实际结果另补。

## 2026-10-28 — 用户授权Phase6最终验收与Private同步

- 用户已查看Phase6开发/独立审查与MIT，授权最终验收、正式Commit、安全合并main、普通Push、Ubuntu/Windows准确SHA CI核实及必要修复。
- 已fetch核对现有Private仓库与main基线2f6b18c；85审查hash中仅3份已记录MIT措辞文档变化，生产代码/测试/配置/构建脚本一致。
- 本轮实际再跑完整测试、离线用户流程和独立安装；结果完成后补记，不提前宣称远端通过。
- 不Force Push、不改变可见性、不创建正式v1.0.0 Release；完成后停止，等待用户亲自体验验收。


## 2026-10-28 — 用户确认 MIT 许可证

- 用户明确选择 MIT；现有 LICENSE 与 pyproject 的 MIT 元数据保持一致，无需修改许可证正文。
- README、第三方声明、架构、变更记录、发布准备及验收报告将许可证草案更新为用户已确认选择。
- 第三方软件、Yahoo/Nasdaq/French 数据与资源许可限制不变；未授予额外数据再分发权限。
- 独立审查原报告/hash保留为历史快照，补充本次仅文档措辞变化说明；金融逻辑、测试与依赖不变。
- 继续保持未Commit/Push、不修改main、不公开仓库或创建Release。


## 2026-10-28 — Phase 6 本地交付与独立审查完成（0.7.0，未提交）

- 增加doctor/workspace/workflow统一入口、严格可读Paper输入、显式目标、计划/摘要/估值/现金/换汇服务。
- 统一合成演示复用股票池/过去动量/独立USD回测/CAD账户核心；审核、成交、重试、收盘变价变汇率、恢复、报告完成。
- 可选因子和ML保持独立证据口径；开发选定Logistic的ML→Paper预览保持pending_review且零成交，因子不直接下单。
- CLI+本地HTML索引/全文件哈希验证；暂缓Streamlit，不增加运行时依赖。原native schema5与所有旧命令保留。
- 英文README、USER_GUIDE、CODE_WALKTHROUGH、CONTRIBUTING、RELEASE_READINESS、架构/CHANGELOG/验收完善。
- MIT作为本地未发布许可证草案，THIRD_PARTY_NOTICES区分软件/数据，57锁定依赖元数据无安装版本不符；Windows无Linux专属NCCL。
- 原609测试两次通过，新增80通过，最终689 passed in46.87s；Ruff lint/format、7种配置与help、锁检查通过。
- 离线sdist/wheel、sdist重建、双wheel源码外干净venv安装、base与完整factor/ML/Phase6工作流均通过。
- 无.git/work/.venv的新源码副本在含空格路径locked离线安装，完整流程63文件哈希验证通过；初次依赖配置仍需网络/预置cache。
- 完整3000 CAD演示：CAD2367.97、USD0、SYN_A37股/SYN_B1股，收盘FX1.30，NAV2971.1700，5事件/2成交，无风险违规，重试恢复一致。
- 单独独立审查80测试与混合CAD/USD Fraction独算NAV2929.9000通过，异常目标/FX/行业/审核不改变状态。
- 最终85文件审查hash与工作文件核对；仅许可证脚本格式变化已复核，行业age表述已修正，无未解决可操作P1/P2/P3。
- 核心限制保留：真实PIT/幸存者/公司行为/日历/OOS未认证，贪心整股规划可能显著低于目标并留下较高现金。
- CI配置扩展但Phase6远端未运行；main/origin-main/HEAD仍2f6b18c，不Commit/Push/公开/Release，等待用户验收。
- PHASE_6_REPORT记录完整命令、证据、安装/演示与发布准备；独立报告及hash保存在docs/reviews/phase6。


## 2026-10-28 — Phase6正式开始（用户授权，未提交）

- 完整核对AGENTS、PROJECT_PLAN、README、开发历史、Phase5验收及实际CLI/研究/组合/Paper接口。
- 工作区初始干净，fetch后main/origin/main均2f6b18c6218b8ac9b529c5bc7f69ee875fc252c5，Private/默认main正确。
- 创建codex/phase-6-product-integration，main和历史分支保留，不Commit/Push/公开仓库/Release。
- Python3.12.14、uv0.13.6，locked离线sync通过，基线609 passed in33.26s。
- 目标：环境诊断、工作区模板、统一离线演示、可读Paper输入/摘要/估值入口、报告索引/校验、英文README及代码导读。
- 取舍：暂不添加Streamlit，使用共享服务CLI和本地HTML索引；基础运行时不新增第三方依赖。
- 保留真实PIT/OOS/成员/退市/日历/公司行为限制；因子仍描述性，ML验证和Paper明确分支，不把诊断直接当订单。
- 项目许可证向用户征求偏好，第三方软件/数据许可分别检查；本阶段完成后安排独立审查。

## 2026-10-28 — Phase5正式同步，真实双平台CI通过

- 正式提交8904e112171306c7039a550c5ae91f187b37c9c0，feat: implement CAD portfolio accounting and paper trading。
- 32文件经完整609测试/锁/Ruff/构建/双wheel安装/敏感检查后提交，安全快进main并普通原子Push main/Phase5成功。
- 远端与本地均8904e11；Private、默认main及Phase2/3/4历史保留，无Force Push/Release。
- Push后两次无自动run记录，通过现有active workflow_dispatch实测40759391233，准确headSha8904e11、success。
- Ubuntu/Python3.12.15：609 passed in74.01s；Windows/Python3.12.10：609 passed in85.48s。
- 两平台Ruff/93文件format、锁/CLI/样例、构建、sdist重建、两个wheel源码外独立安装和Paper恢复全部通过。
- 读取两个完整job日志与准确SHA，未挪用本地/旧CI；本轮无CI故障或生产算法修复，保留上游Node/runner提醒。
- 原25测试文件不改；46生产源码与13独立审查证据一致，完整3000 CAD演示恢复/重复不扣费及NAV2949.10对账通过。
- README/验收/CHANGELOG/架构/AGENTS补记实际结果；其后文档收尾SHA的CI另行实际核查，不冒称8904e11结果适用于任意提交。
- 本阶段收尾后停止；不开始Phase6、不创建正式Release，不扩大真实PIT/OOS/公司行为/日历认证。

## 2026-10-28 — Phase 5 最终验收与Private同步获授权

- 用户原则批准最终验收、完整合成演示、必要缺口测试、正式Commit、安全合并main、普通Push及真实双平台CI检查/问题修复。
- 实际fetch起点main/origin/main/HEAD仍0e4ca96；Private与默认main正确，无其他工作被覆盖。
- 46生产文件/13独立证据hash全部一致，无需重做独立审查；只新增1项联合回归，生产算法不改。
- 复用旧动量研究和Paper CLI：3000 CAD→审核→3fills→NAV2994.48；合成价格/FX变化后NAV2949.10。
- 现金1238.08 CAD/USD0，29股CAD_B/44股USD_A/17股USD_C；成本5.52精确对账，无风险超限或透支。
- 同订单重试不变，VALUE不新增费用；新Python进程恢复完整账户一致，原始输入/快照/报告均仅本地。
- 全量609 passed in32.81s，Ruff lint/93文件format、locked sync/lock通过；旧425及183新增不删减。
- 版本保持0.6.0；正式消息feat: implement CAD portfolio accounting and paper trading；实际提交/Push/CI结果完成后补记。
- 不连接broker、不真实交易、不Force Push、不改变Private、不开始Phase6、不创建Release。

## 2026-10-28 — Phase 5 本地完成，独立审查修复复验通过，等待用户验收

- 0.6.0，codex/phase-5-cad-paper；HEAD/main/origin/main保持0e4ca96，无暂存/Commit/Push/Release/Phase6。
- 完成风险/行业/现金/交易限额、USD/CAD历史FX及成本、CAD账本、人工审核计划、SQLite持久Paper和幂等重启。
- CAD历史synthetic harness与Paper复用planner/模拟/估值；旧USD、Universe、Factor、ML功能保留。
- 全量608 passed in34.69s（原425保留、新增183）；锁定sync/lock、Ruff lint/93文件format通过。
- wheel/sdist、sdist离线重建、直接/重建wheel各自干净venv且源码外Phase0–5/资源/恢复检查通过。
- 独立初审发现高固定费卖单、synthetic混real、同刻公司行为、history估值时钟及native验型缺陷；
  主代理修复，全部反例正式回归且由独立代理重新核实，不将初版状态写成无发现。
- 最终独立214测试、1000 Fraction数值、8线程24重复execute（只4事件3fills）通过；无未解决可操作P1/P2/P3。
- 主代理核对46生产源码和13审查证据hash一致；原425测试文件/原计划不改，32候选文件敏感模式未检出。
- 默认3000 CAD合成账户3fills，终现金1238.08 CAD/USD0，NAV2994.48；费用/滑点/FX损耗总5.52精确对账。
- 输入/结果hash、链及ledger_head同事务保存，进程中断恢复、重复成交/费用、尾部删除/算法漂移均有测试。
- 报告PHASE_5_REPORT、PAPER_TRADING、架构/CHANGELOG/README更新；证据work/phase5-closeout及independent-review。
- 本地软件验收不等于真实PIT/OOS或市场策略认证；无本阶段远端CI，完整权益/同刻多行动/复杂公司行为仍不支持。
- 保留全部历史和阶段分支，停止等待用户确认；后续提交/Push/CI或Phase6须另行授权。

## 2026-10-28 — Phase 5 正式开始（用户授权）

- 完整读取协作约定、项目计划、README、开发历史、Phase 4 验收及现有 domain/组合/执行/ML 接口。
- 起点工作区干净；实际 fetch 验证 main/origin/main 均为 0e4ca9677ed2e53dd2641b0f49157de88030aaa8。
- 从 main 创建 codex/phase-5-cad-paper；保留各历史分支，不修改 main，不 Commit/Push。
- Python 3.12.14 / uv 0.13.6，使用 work/bin/uv.exe 与已有锁定环境；不新增第三方依赖。
- 设计：Decimal CAD 总账、多币种现金、带可得时间的历史 FX、Top-K 保守约束、人工审核计划、
  SQLite 原子事件账本及重放；USD 原接口保留，新增 CAD 历史模拟和 Paper 复用纯计算。
- 真实 PIT/成员/退市/日历仍无认证；历史执行入口仅 synthetic。无券商、真实订单或 Phase 6。
- 完成后安排独立 Code Review，验收命令与实际结果另补，不预写通过状态。

## 2026-10-27 — Phase 4 最终验收通过，真实双平台 CI 成功

- 功能提交05d190070ddd695c5fa1f72f316a601609c63db5已安全快进main并普通原子Push main/Phase4，完整历史保留。
- 真实运行40602662692，headSha精确05d1900、conclusion=success：
  https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40602662692。
- Ubuntu/Python3.12.15：425 passed in65.61s；Windows/Python3.12.10：425 passed in81.29s。
- 两平台Ruff/76文件format、锁/配置/CLI、构建、sdist重建、两个wheel干净环境源码外Phase0–4全部通过。
- Push未观察到自动运行，沿用现有workflow_dispatch实测；不声称Push自动触发已验证。无CI失败或业务修复。
- 独立审查36生产源码SHA一致，144组合/3024边界fold与未来扰动证据核实；6项补测只扩展验证，不改算法。
- 本阶段正式验收范围仅合成USD软件正确性，无真实PIT/OOS、校准概率或策略盈利认证。
- 验收/README/AGENTS/架构/CHANGELOG补记实际提交与CI；该文档提交后再核对其自身CI和Git状态。
- Private、Phase2/3历史保留；不Force Push、不创建Release、不进入Phase5，完成后停止。

## 2026-10-27 — Phase 4 正式提交、快进合并及 Private Push

- 正式提交05d190070ddd695c5fa1f72f316a601609c63db5，feat: add leak-safe ML and walk-forward validation。
- 26文件，425本地测试与审查核实/针对性补测/安装验收全部通过后创建；未改生产数学或时间算法。
- Phase4安全快进合并main，main/Phase4普通原子Push成功；远端/本地指针一致，工作区当时干净。
- 实际核对Private、默认main；Phase3仍65f1bca、Phase2仍ba26bea。未Force Push、公开仓库或创建Release。
- Push后未观察到自动CI，沿用workflow_dispatch实际运行40602662692，准确SHA05d1900；结果后补。
- 原独立审查文件SHA已记录在验收报告，未重写其结论或证据，不将3024边界检查混称市场实验。

## 2026-10-27 — Phase 4 最终验收收尾获授权

- 用户授权核实审查证据、必要补测、正式Commit、安全合并main、普通Private Push及Ubuntu/Windows真实CI检查/修复。
- 实际fetch核对本地/远程main仍65f1bca，Private与默认main正确；原审查36个生产Python哈希全部一致。
- 原3024 folds来自144参数组合×7外折×(本折+2内折)，仅边界检查，不是3024市场试验。
- 明确Lasso为训练内L1收益回归；selector为VarianceThreshold；分类score未校准。
- 明确合成Holdout已反复运行用于软件验证，程序冻结不证明真实研究中未触碰最终测试集。
- 补充5模型外层标签翻转及全流程Holdout特征+标签扰动，共6测试通过；生产算法未改。
- 本轮全量425 passed in32.31s（原330保留+95新增），锁定sync/lock、Ruff lint/format通过。
- wheel/sdist、sdist离线重建、两个wheel干净venv源码外Phase0–4安装检查全部通过；CLI帮助/三配置/因子与ML运行成功。
- 26候选文件敏感模式未检出，原计划/原330测试/36生产文件一致，发行包无work/outputs/venv；Git/CI另补实测结果。
- 不进入Phase5、不发布Release；真实PIT/OOS、历史成员/退市/公司行为/日历等限制全部保留。

## 2026-10-27 — Phase 4 本地完成，独立审查通过，等待用户验收

- 0.5.0，codex/phase-4-ml-walk-forward；main/origin/main/HEAD仍65f1bca，未Commit/Push/进入Phase5。
- 已实现可追溯特征/标签、按全局日期expanding/rolling、整日期purge、gap/前置安全embargo。
- prior/Logistic/连续收益Lasso/RF/CPU XGBoost，训练内Pipeline、嵌套TimeSeriesSplit小网格调参。
- 开发标签跨Holdout排除，开发winner/最终参数冻结后单次Holdout；指标和全模型结果如实保留。
- ML分数复用既有Top-K/整股/next-open/费用/滑点/现金/NAV，与四类基准及0/1/2倍成本比较。
- 不可覆盖JSON/CSV/HTML、完整输入/每内外折/拟合统计/预测/目标/订单/成交/持仓/NAV及哈希。
- 全量最终 **419 passed in 31.33s**，保留原330项，新增89项；禁socket。Ruff、锁定安装与lock通过。
- wheel/sdist、sdist离线重建、直接/重建wheel的干净venv源码外Phase0–4运行均通过。
- 独立只读审查重跑114测试；144参数组合、3024内外fold、906990训练行成员及五模型
  Holdout价格/未来标签扰动无可操作P1/P2/P3发现。报告work/phase4-independent-review/REVIEW.md。
- 审查后生产源码SHA逐项一致；额外将未来标签单独翻转的五模型检查保留为正式回归测试。
- 首次XGBoost参数NaN导致严格JSON拒绝，已显式编码参数缺失标记，未放松特征/预测有限性。
- 新增ml extra由uv解析，原有第三方包版本不变；Python3.12.14/uv0.13.6，元数据/实际拟合验证。
- 仅合成USD软件验证；真实PIT/成员/退市/日历/公司行为、统计独立性、真实Holdout治理仍待证据。
- CI配置已扩展但本轮无Commit/Push，Phase4远端Ubuntu/Windows CI尚未执行；不挪用Phase3成功。
- 命令、实际合成结果、设计差异与限制见PHASE_4_REPORT/MODEL_VALIDATION。停止等待用户验收。

## 2026-10-27 — Phase 4 正式开始（用户授权）

- 完整核对计划、README、AGENTS、开发历史、Phase 3 验收与相关源码；基线 330 passed in 9.35s。
- 当前为主仓库唯一工作树；远端 Private / main 与本地一致，65f1bca；已从 main 创建 codex/phase-4-ml-walk-forward。
- 实际读取 GitHub Actions 40597881595，确认准确 SHA 139d17f 两平台 success；不挪用为 Phase 4 CI。
- 范围：可追溯特征/标签、全局日期划分、purge/gap、嵌套调参、Pipeline、模型指标、合成信号回测与报告。
- 真实 PIT 与历史成员证据仍不足，只用合成 USD 数据验证。因子诊断禁止进入历史信号。
- 版本开发至 0.5.0；仅新增本阶段 ml extra，uv 正式解析锁。完成后独立 Code Review，不 Commit/Push/main/Phase5。

## 2026-10-27 — Phase 3 已验收同步，修复后双平台真实 CI 通过

- 功能提交b929b8f29ca2e0126112241c907dc0b44ddb11a0及CI安装修复139d17f2feb0ebce537399e3c0f145a123db79a6
  均已在Phase3分支提交，完整历史快进进入main，两个分支普通原子Push成功；Phase2仍保留ba26bea。
- 原Private仓库、默认main和现有历史保留；没有Force Push、改变可见性、创建Release或进入Phase4。
- 修复前后用同一冷缓存验证旧安装失败/新安装通过；修复后本机330 passed in 11.35s，Ruff/锁/构建通过。
- 真实成功运行：https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40597881595，准确SHA为139d17f。
  Ubuntu/Python3.12.15：330 passed in 18.65s；Windows/Python3.12.10：330 passed in 26.71s。
  两平台Ruff、配置/CLI、合成因子研究、构建、sdist重建与直接/重建wheel的干净安装全部成功。
- Push未观察到自动触发，本次通过现有workflow_dispatch验证；首次失败40597082932保留，不掩盖冷缓存问题。
- 验收/README/CHANGELOG/协作状态记录真实提交及CI；最终文档提交后仍核对其自身CI与远端同步，结果见Actions与收尾摘要。
- 验收范围保持事后描述性研究；数据/PIT/OOS限制不变，完成本轮后停止等待后续明确授权。

## 2026-10-27 — Phase 3 首次 Push 与真实 CI 安装修复

- 正式功能提交b929b8f29ca2e0126112241c907dc0b44ddb11a0已创建；main快进合并，main与Phase3分支普通Push成功。
- 仓库仍Private、Phase2分支和原历史保留；没有Force Push。Push未观察到自动运行，显式调度已有CI。
- 首次真实运行40597082932：两平台330测试及Ruff/CLI/构建通过，但都在独立wheel安装的离线依赖解析失败。
- 根因是requirements按包名解析需要独立registry缓存；初始锁定sync的直接wheel URL缓存不足以保证这一点。
- 全新本地缓存重现旧流程contourpy缺失；修复验证脚本直接按lock给隔离venv离线sync依赖，保留被测wheel。
- 增加isolated Python的wheel来源与venv位置断言；不改业务/测试/依赖版本，不移除任何检查。
- 同一冷缓存下两个wheel、sdist重建及Phase0–3验证通过；日志保留，后续继续验证实际远端CI。

## 2026-10-27 — 用户正式验收 Phase 3，授权提交与私有仓库同步

- 最终独立复核确认 R1–R5 全部PASS，330测试通过；用户正式验收范围仅为事后描述性因子研究。
- 复核独立检查21,538个时间组合、26组窗口QR、原CLI反例、晚下载和证据不足限制，未发现新增阶段阻塞问题。
- 本轮仅文档/状态收尾、正式Commit、合并main、普通Push及CI检查修复；不进入Phase4、不创建产品Release。
- 当前唯一worktree含全部最终修复；Python源码与最终复审wheel一致，保留现有未提交开发成果及完整历史。
- 已在线核对仓库仍Private；本地/远程main及Phase2均为ba26bea，初始无分叉或远端待整合变更。
- 依据既有gitattributes，将新增两份合成因子CSV及新增metadata统一LF，解析数值/含义保持一致。
- 已更新验收/README/协作范围/架构/CHANGELOG；PIT、第三方价格/复权、日历及统计推断限制均保留。
- 本轮提交前完整测试330 passed in 9.45s；Ruff lint/format、锁一致性、离线锁定同步通过。
- wheel/sdist、sdist重建、两个wheel干净安装及源码外Phase0–3命令/资源检查通过；37个候选文件敏感模式未检出。
- 真实数据/缓存/虚拟环境/输出/凭证仍被忽略；Git索引逐字节复核后正式提交。真实Git/CI结果另补记，不提前标为通过。

## 2026-10-27 — R5 定点整改完成，等待专项独立复核

- 已读取第二次独立审查报告及原 CLI 复现材料；R1–R4 已 PASS，本轮仅修复 R5，不改写历史审查证据。
- 根因：时间顺序检查没有验证事件与本地 session 日期一致；晚下载的合法顺序掩盖了跨月错误标签。
- 生产仅改 data_contracts.py / factor_returns.py：按已支持美国交易所本地日期及来源 timestamp_basis 校验；
  明确矛盾隔离且因子入口退出 2，未知事件/来源/时区数据库明确标记仅描述性、不适用严格历史流程。
  保留晚下载及真实 available_at，不把观测上界伪装为收盘事件，不简单比较 UTC 日期。
- 新增32个回归/边界案例；原298项与20个测试文件全部保留，最终 **330 passed in 9.52s**。
  同一最终测试文件对旧/新包的四项主反例为4 failed/4 passed，哈希一致；未放宽断言。
- 原审查 good/bad native CSV 和配置重新通过公开 CLI：good仍24月退出0；bad隔离1条并退出2，无成功报告。
- 日28/月13个尾随窗口与独立QR一致；未来扰动不改变较早窗口。OLS、模型比较及Rolling函数哈希不变。
- 20组有理数/QR/显式推断参考复核通过；真实缓存socket禁用重放：日689/564窗，月33/10窗，分析与原报告一致。
- Ruff、锁定离线同步、锁一致性、CLI/配置、构建、sdist重建、双wheel干净安装的Phase0–3验证通过。
- 新增测试首次有1项构造顺序错误，修正测试输入按declared直接构造，断言保留；失败与后续日志均保留。
- 更新验收报告、数据政策、方法、架构、README/CHANGELOG/当前协作范围；不改依赖、缓存或原始计划。
- 证据位于work/phase3-r5；外部来源本轮没有新下载，远端CI未运行，PIT/真实收盘/日历等限制保留。
- 保持0.4.0及独立开发分支，不Commit/Push，不进入Phase4；停止等待R5独立复核。

## 2026-10-27 — Phase 3 四项整改完成，等待第二次独立审查

- R1：完整请求月末网格与 Rolling 兼容补齐，双边/边缘缺月不扩窗；R2：月频清单与报价冲突阻断。
- R3：校验 provider_adjusted + close，拒绝不实纯价格标签；provider_ohlc 保留口径不确定性。
- R4：精确十进制移位，不继承外部 context；因子缓存 v2 隔离旧精度相关值，旧文件保留。
- 四个主反例实测 4 failed → 4 passed；新增 28 个回归/边界案例，完整测试 **298 passed**。
- 原 19 个测试文件及五个 OLS 相关函数源码哈希保持不变；20 组独立数学参考复核通过。
- Ruff、锁定安装/锁文件、构建、sdist 重建和双 wheel 干净安装验证通过；没有改依赖。
- 本轮重新获取 AAPL 709 行与 French 日/月数据；日频 689 样本/564 窗，月频 33 样本/10 窗，
  均无失败窗口；离线结果相同，真实日历漏 1/31 的冲突明确拒绝。
- 精度边界测试曾继承 sticky flags，修正测量初始化并增加保持旧 flags 用例；断言未放宽，日志保留。
- 整改细节、文件、红绿测试与真实证据见 PHASE_3_REPORT 末节和 work/phase3-remediation/。
- 生产改动仅三个因子文件；不改 OLS 数学，不删除原审查材料，不 Commit/Push，不进入 Phase 4。
- Phase 3 暂缓正式验收，停止等待用户安排第二次独立审查。

## 2026-10-27 — Phase 3 独立审查整改开始

- 已完整读取 work/phase3-independent-review/REVIEW.md 及脚本/JSON；报告不在仓库根目录。
- Phase 3 暂缓验收，仅整改 R1/R2 两项 P1 与 R3/R4 两项 P2，不重做阶段、不进入 Phase 4。
- 新增四个针对性回归测试，修复前实际结果为 4 failed；证据 work/phase3-remediation/red-tests.log。
- 根因分别为缺失月从时间网格消失、清单与报价矛盾未拒绝、Close 分支忽略 price_basis、
  百分数解析继承调用方 Decimal context。修复限制在因子时间网格、收益校验和解析/缓存版本。
- 已记录五个 OLS/协方差/推断相关函数及 19 个既有测试文件的源码哈希，后续复核保持不变。

## 2026-10-27 — Phase 3 本地完成，等待验收

- 0.4.0，分支 codex/phase-3-factor-diagnostics；仅本阶段因子研究，无自动 Commit/Push。
- French US FF3 + Mom 日/月频、百分数/RF/日期契约、来源与读取快照；明确事后归因。
- 股票收益与超额收益、同样本 FF3/FF4 OLS、经典/HC3 推断、条件数/VIF/残差诊断。
- 尾随名义期间滚动、缺失不扩窗、失败窗口可见、未来扰动不变，历史信号入口阻断。
- prd research run 与统一审计输出，JSON/CSV/HTML/SVG/PNG，快照/指纹/最后完成标记。
- 全新锁定环境全量 **270 passed**，保留原 208；Ruff lint/format、lock、构建及双 wheel 独立安装通过。
- 真实 French 日频 26,338 行、月频 1,203 行；AAPL 日频共同样本 689、月频 33；离线缓存全部命中。
- 修复实测 yfinance 惰性 Mapping 兼容、基础安装缺少 extra 的错误路径；保留身份校验与上游警告。
- Phase 3 CI 已配置但未远端执行；macOS/Linux 本阶段未实机验证，不把既有 Phase 2 CI 当成本阶段结果。
- 方法、实际命令、失败修复和限制见 PHASE_3_REPORT / FACTOR_RESEARCH；原计划保持不变。
- 停止等待用户验收，未进入 Phase 4。

## 2026-10-27 — Phase 3 开始（用户正式授权）

- 从干净的 main / ba26bea 开始，独立分支 codex/phase-3-factor-diagnostics；保留既有历史。
- 已复核计划、协作约定、README、日志、源码和环境；基线 208 测试通过。
- 本阶段仅因子数据、收益对齐、FF3/Carhart FF4 诊断、Rolling Exposure、CLI 与审计报告。
- French 来源发布时间未验证，下载历史只作事后归因，不进入交易信号或合成执行接口。
- 将以已知答案、共同样本、单位/频率、统计异常和未来扰动测试验收；不自动提交或 Push。

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
