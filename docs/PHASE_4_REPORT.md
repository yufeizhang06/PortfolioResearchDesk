# Phase 4 验收报告 — Machine Learning & Walk-Forward Validation

> 历史验收记录：下文仅描述该阶段列明版本的检查与限制；当前功能见
> [README](../README.md#current-development-status)，后续证据见[文档索引](README.md)。

日期：2026-10-27（America/Toronto）。开发版 0.5.0。
分支：`codex/phase-4-ml-walk-forward`；稳定基线 `65f1bca6ac0459c77de598957779db2ddcd7780b`。
**历史验收结论：Phase 4 技术验收通过，仅限合成 USD 软件验证。准确 SHA 的 Git/CI 结果见末节；当前功能见[文档索引](README.md)。**

下文 418/419 测试、待验收和未提交状态保留开发历史；本轮最终结果为425测试，见末节。

## 开始前的独立核查

- 已读取 AGENTS、完整 PROJECT_PLAN、README、DEVELOPMENT_LOG、Phase 3 验收和相关实际源码/测试。
- 验收在原仓库 checkout 中执行；独立审查材料与该 checkout 的文件指纹另行核对。
- 开始时工作区干净；实际 fetch 后本地 main、origin/main 均为 65f1bca；从该提交创建独立开发分支。
- 实际 GitHub 查询确认 `yufeizhang06/PortfolioResearchDesk` 为 Private、默认 main。
- 实际读取 Phase 3 Actions 40597881595：准确 SHA 139d17f、Ubuntu/Windows 均 success。
  330 项各平台结果见既有报告；本轮本地基线重跑 330 passed in 9.35s。
- 不将 Phase 3 CI 冒充最新文档提交或 Phase 4 CI。原 PROJECT_PLAN SHA-256 保持
  `1f208c70b41aeaecfac45f1e38bcd2d3ff674f6eb1868352b45fd9eb40f752bb`。

## 范围与验收映射

| 技术要求 | 已实现与验证 |
|---|---|
| FR-05 可追溯 FeatureRow / LabelRow | 时间区间、可得/已知、固定来源/schema、next-open 收益标签、未知尾部排除 |
| 少量时间序列特征 | 5/20/60 收益、20/60 波动、20 日 log 流动性、固定合成市场相对收益；独立 Fraction 手算 |
| Baseline / Lasso / RF / XGBoost | prior、Logistic、连续收益 Lasso、RF、CPU XGBoost，小网格与固定种子 |
| FR-09 TimeSeriesSplit / Walk-Forward | 全局日期 expanding/rolling；外层开发与最终 Holdout；内层 TimeSeriesSplit 再 purge |
| 标签重叠、Gap / Embargo | 整日期 purge；标签结束/已知均早于验证首日，额外前置日期空档，无未来训练 |
| Pipeline / 调参 | Imputer、Scaler、VarianceThreshold、模型全在对应训练内 fit，内折 F1 选择参数 |
| 六项分类输出 | Accuracy、Precision、Recall、F1、ROC-AUC、混淆矩阵；单类 AUC=null、零分母明确 |
| FR-08 保存 OOS 预测 | 逐资产/日期、fold/model/fit_at、分数/目标/标签时间/排除；每内/外折训练统计 |
| Holdout 独立性 | 开发 winner/参数冻结，跨 Holdout 开发标签排除，Holdout 无调参/重训/选优 |
| 现有引擎整合 | 可选 SignalProvider，Top-K/整股/next-open/成本/现金/NAV 复用；旧默认逻辑保留 |
| 净表现公平比较 | 同阶段模型、Cash、Buy-Hold、Equal-weight、Momentum；0/1/2 倍成本情景与账本 |
| FR-15/17 CLI / 可复现 | ml run / config validate --kind ml；JSON/CSV/HTML、输入/源码/配置/依赖指纹、最后完成标记 |
| 第 4.5 节反泄漏 | 未来价格/标签、验证分布扰动、全局日期边界、未知/跨界标签、未来特征/晚可得拒绝 |
| 原有时间/数据门槛 | 原同日执行、当前成员/PIT阻断及因子入口测试均保留并通过；Phase 3 不进入信号 |

新增七个 ml_* 模块和包内/configs 示例、四个测试文件；小幅扩展 backtest.py、cli.py；
更新 README/协作/架构/日志/CHANGELOG、CI 和发行包验证。没有改写旧因子/数据/执行算法。

## 关键设计与限制

数学、日期定义及完整调参协议见 [MODEL_VALIDATION.md](MODEL_VALIDATION.md)。
严格边界：全部训练 label_end 与 known_at 都早于验证首日 UTC 零点，而非允许验证当天行情参与训练。
滚动窗口和 gap/embargo 按日期数；purge 后实际样本数可审计。embargo 是纯向前验证的额外前置缓冲，
不声称实现双向 CV post-test embargo。模型先训练，再预测；所有拟合都不接触外层验证或 Holdout 标签。

本阶段 **只接受 synthetic USD 面板**。真实 PIT、历史成员、退市、公司行为账本和权威日历仍未认证，
不引入真实历史交易信号。固定 weekday/UTC 时刻不是交易所日历。因子诊断结果没有进入 ML。
Lasso 是连续价格收益回归；其余是分类，class scores 未校准。重叠标签非 IID，不提供显著性承诺。
分类标签未扣费；实际成交受整股/成本/缩单影响；尾部持仓按收盘估值，不强平。
ML/Momentum Top-2；Equal-weight/Buy-Hold 三资产；stage 分别从相同现金开始，不混合开发和 Holdout 资金。

## 运行环境与依赖

Python 3.12.14，uv 0.13.6；PATH 不含 uv，使用 `work/bin/uv.exe`。
专用环境 `work/phase4-venv`，缓存 `work/uv-cache-phase3`；无全局 Python 改动。
新增可选 `ml` extra，锁由 uv 正式解析；原有第三方包版本未升级（项目版本0.4→0.5），总锁记录58个包。

| 包 | 实际安装版本 | Requires-Python |
|---|---|---|
| scikit-learn | 1.9.1 | >=3.11 |
| XGBoost | 3.4.1 | >=3.12 |
| NumPy | 2.5.4（保留） | >=3.12 |
| SciPy | 1.18.1（保留） | >=3.12 |

已核查官方 TimeSeriesSplit、Pipeline/泄漏、Lasso、安装兼容和 XGBoost 文档；安装元数据和实际拟合通过。
XGBoost 指定 CPU、hist、n_jobs=1；默认发行依赖在 Linux 可含 NVIDIA 运行库，但本实现不调用 GPU。
基础包依赖仍为空；缺 ml extra 在取数/拟合前报用户错误退出 2。

## 实际执行命令与结果

PowerShell 任务环境（不是全局设置）：

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) 'work/uv-cache-phase3'
$env:UV_PROJECT_ENVIRONMENT = 'work/phase4-venv'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
```

下列 `uv` 在本机用 `work/bin/uv.exe`：

```text
uv sync --locked --extra data --extra factors --extra ml --offline
uv lock --check --offline
uv run --locked --offline pytest -p pytest_socket -q --basetemp work/phase4-full-tests -p no:cacheprovider
uv run --locked --offline ruff check .
uv run --locked --offline ruff format --check .
uv run --locked --offline prd --help
uv run --locked --offline prd config validate --kind ml --config configs/example_ml.toml
uv run --locked --offline prd ml run --run-id phase4-validation
uv build --offline --no-build-isolation --out-dir dist/phase4
uv run --locked --offline python scripts/verify_distribution.py dist/phase4 --uv <uv绝对路径> --with-factors --with-ml
```

- 初次全量 **418 passed in 27.82s**；补充未来标签单独翻转的正式回归后，
  最终 **419 passed in 31.33s**：原 330 项全部保留，新增 89 项；测试禁 socket。
- Ruff lint/format、锁一致性和锁定离线同步通过。
- 独立数值：Fraction 价格收益/样本方差/相对收益/标签；Lasso 单特征软阈值闭式解；
  分类指标手工混淆矩阵与含 ties 的 pairwise ROC-AUC；逐成交独立重建现金/持仓/NAV。
- 18 组 horizon × gap/embargo × expanding/rolling 对全部外/内折逐项核查。
- 五模型验证集分布扰动不改训练统计与内层调参；单类训练显式 fallback；未知/非法输入阻断。
- 全流程未来价格/标签扰动不改早期预测/目标；Holdout 首日起所有 OHLC 扰动不改开发审计/冻结方案。
- 报告逐文件 SHA、不可覆盖、I/O 失败无完成标记、CLI JSON/退出 2 有测试。
- 默认 CLI complete；报告 `outputs/ml/phase4-validation/`。固定 Run ID 已存在，复验请换 ID。
- wheel/sdist、sdist离线重建、双wheel干净venv安装及源码外Phase0–4均通过；远端Phase4 CI未执行。

首次 CLI 报告遇到 XGBoost 默认参数含原生 NaN missing 标记，严格 JSON 正确拒绝。
已将该**参数元数据**序列化为明确字符串，仍禁止特征、预测和指标的非有限数值；未放宽 JSON。
最初误用 PowerShell 未展开的 pytest 文件通配符导致零测试，改为明确文件名后 88 项实际通过。

## 默认合成结果（实际计算，仅软件验证）

开发日期 120 × 3 资产共 360 预测，342 完整开发标签；Holdout 40 × 3 共 120 预测，102 完整标签。
跨 Holdout 的 18 个开发标签和末尾 18 个未知标签明确排除。开发 F1 选择 Logistic，未按 Holdout 选优。

| 模型 | Holdout n | Accuracy | F1 | ROC-AUC | 合成 Holdout 净收益 |
|---|---:|---:|---:|---:|---:|
| Dummy prior | 102 | 0.549020 | 0.708861 | 0.500000 | 0.640% |
| Logistic | 102 | 0.852941 | 0.869565 | 0.875388 | 1.089% |
| Lasso | 102 | 0.852941 | 0.876033 | 0.880435 | 1.089% |
| Random Forest | 102 | 0.813725 | 0.831858 | 0.869177 | 1.639% |
| XGBoost | 102 | 0.823529 | 0.839286 | 0.873641 | 1.553% |

同阶段合成净收益：Cash 0%，Buy-Hold/Equal-weight 各 0.606%，Momentum −0.662%。
这些是固定人工生成模式上的实际计算，不是市场证据、真实上涨概率或可投资收益。
合成树模型净收益较高不能据此替换开发选定的 Logistic。

## 与计划书差异、风险及后续依赖

- 市场代理是固定三合成资产收益均值，不是可投资市场指数；少量特征而非盲目扩因子。
- 不新增真实行情回测：数据证据不足时采用合成软件验证，并在 CLI/HTML/JSON 显著声明。
- 未实施概率校准、置信区间、真实公司行为/日历、CAD/FX、行业约束、Paper 持久化或 UI。
  这些不能由本阶段测试证明，后续阶段需独立证据。
- 公开数据/时间契约不能检测把全部时间与未来值一起伪造成自洽输入；仍需来源证据与审查。
- final plan hash 是审计，不是研究者事先登记证明；反复真实 Holdout 试验会失去独立性。
- GitHub Actions 已更新 Ubuntu/Windows 的 ml 安装/测试/CLI/发行检查；本轮没有 Commit/Push，
  因此 **Phase 4 远端 CI 尚未运行，macOS 未实机验证**。
- 该本地检查点先于提交与远端 CI；最终独立审查和同步结果见末节。

## 独立 Code Review 与最终验证

独立代理已只读完成审查，未发现可操作的 P1/P2/P3 缺陷；审查未修改生产或正式测试。
原报告、独立脚本与 results.json 在 `work/phase4-independent-review/`，仅留本地。

- 审查自行重跑 ML/回测/执行相关 **114 passed in 17.50s**。
- 独立检查 144 参数组合、3,024 内/外层 Fold、906,990 训练行成员，确认区间、known_at、
  全局日期、整日期 purge 和安全空档；不以正式测试通过代替边界推导。
- 五模型将全部 Holdout 首日起 OHLC 翻倍，冻结方案、开发指标/净值及最终训练统计不变。
- 五模型直接翻转 179 个在未来 cutoff 后才已知的标签，所有更早 OOS 分数与目标组合不变。
- 主代理逐项复核审查保存的生产源码 SHA-256，审查后无变化；额外保留未来标签直接扰动正式测试。
- 审查明确限制：只支持合成USD时间正确性；不认证真实PIT、来源声明、开盘流动性、IID显著性或真实Holdout治理。

构建/安装实际通过：`dist/phase4/`，日志 `work/phase4-distribution.log`，最后明确
`PASS: sdist rebuild, both wheels, clean install and CLI/resources on 3.12.14`。
两种wheel都在源码外执行Phase0–4，包含五模型及完成标记，基础安装缺extra退出2，
安装锁定extra后验证wheel来源/venv位置，防止editable源码掩盖打包缺失。
hardlink回退复制、子环境VIRTUAL_ENV提示及源码内缓存提醒保留；不影响结果。
最终文档/测试补记后的同版本发行包另在 `dist/phase4-final/` 构建复核；生产Python与已验证安装一致。
该轮直接/重建wheel源码外Phase0–4干净安装也已实际通过，日志 `work/phase4-final-distribution.log`。
最终源码/包清单审计为 `work/phase4-final-audit.json`；未发现work/outputs/venv混入发行物。

该历史检查点完成了 Phase 4 本地实现与独立技术审查；之后的提交和准确 SHA
远端 CI 结果单独记录于下文，不由本地结果推断。

## 最终验收 — 审查证据核实

本轮已核对原审查报告、probe_review.py、results.json 及当前源码。36 个生产 Python 文件
SHA-256 与原审查记录逐项一致，没有生产算法变化；不重新进行整轮独立审查，也不改原审查材料。
实际 fetch 确认当前 main/origin/main 起点均65f1bca，Private身份/默认main正确；
最新稳定文档提交65f1bca的历史CI40598369112也为success，未将其冒充Phase4 CI。

| 重点问题 | 已核实证据与结论 |
|---|---|
| 未来标签重叠 | end_at/known_at 均须早于验证首日UTC零点；跨界、未知、晚知标签整日期purge，gap不能替代该检查 |
| Nested CV | 内层TimeSeriesSplit只看外层已purge训练日期，再次purge；全部Pipeline逐内折重新fit，外层标签不选参 |
| Holdout冻结 | 开发选择winner，最终内层调参后冻结方案；Holdout内不重训、不调参；跨Holdout开发评价标签也删除 |
| 训练内预处理 | Imputer/StandardScaler/VarianceThreshold与模型均在训练Pipeline；五模型分布扰动测试已覆盖 |
| Lasso含义 | Lasso为连续收益回归，L1收缩/置零在训练内；没有独立Lasso SelectFromModel筛选阶段，显式selector为VarianceThreshold |
| Signal/执行 | feature available_at≤decision_at；Signal/下单再次校验；固定已知收盘整股请求，下一显式session开盘成交，不能按未来开盘向上增仓 |
| Classification Score | 保存uncalibrated_class_score；文档不称校准上涨概率；Lasso为predicted_price_return，没有概率校准声明 |

3,024 Fold 的精确来源：12个horizon（1–12）×3个gap（0/2/10）×2个embargo（0/3）×
2种窗口（expanding/100日rolling）=144组合。每组320 sessions、3资产、60日warm-up、
开发初始100日、每折验证20日、最终Holdout40日；6开发外折+1Holdout外折，
每个外折有2内折，即144×7×3=3,024。共检查906,990训练行成员关系。
这些是日期/区间/可得性断言，不代表3,024次模型拟合或3,024个独立市场试验。
独立五模型价格/标签扰动另用240 sessions、Holdout20日；不能混称为该3024折矩阵。

重要限制：程序中Holdout不参与选择、拟合或调参；但合成数据和Holdout已反复运行/查看用于软件开发验证。
没有证据证明真实研究中“开发者从未看过最终测试集”，plan_hash不构成外部预注册。
未来真实实验仍须新冻结协议、未触碰的测试期及PIT证据。此项不阻塞本次**合成软件**验收，
但阻止扩大为可信真实交易策略认证。

### 针对性补充与本轮实际验证

价格翻倍并不必然翻转同区间收益标签，故补充六项正式回归，而不重复完整审查：

- 五模型分别翻转外层验证标签，内层trials/选参/训练统计及外层分数均不变。
- 同时改Holdout特征分布并翻转Holdout标签，五模型冻结方案、开发指标、内层trials/选参/最终拟合均不变，
  而Holdout指标确实变化；证明测试扰动有效。
- targeted-tests.log：6 passed in 12.21s；全量 full-tests.log：**425 passed in 32.31s**。
  原Phase0–3的330项测试文件未改，新增总数95项，测试禁socket；没有删除或放松旧断言。
- uv sync --locked --extra data --extra factors --extra ml --offline、uv lock --check --offline实际通过。
- 完整Ruff lint/format通过；wheel/sdist、sdist离线重建、两个wheel各自干净venv安装及源码外Phase0–4运行通过。
  distribution.log末尾明确PASS，未依赖源码editable安装掩盖遗漏；本轮未改发行检查或CI业务逻辑。
- README所列研究/因子/ML配置、帮助、默认合成因子与显式ML配置CLI均成功；输出只留本地。
- audit.json确认原计划/原330测试/36生产文件保持、26候选文件敏感模式未检出、发行包源码一致且无本地数据/缓存。
- 后续功能提交消息：feat: add leak-safe ML and walk-forward validation。
  后续实际提交、同步及真实 CI 见下文；保留原始历史。
- 全部本轮命令证据在work/phase4-closeout/；未产生任何真实交易、付费资源或正式Release。

后续Phase5仅为计划：组合风险/行业集中度、历史USD/CAD与换汇成本、CAD账本、Paper状态持久化、
幂等模拟订单与重启重放；后续实现见 [PHASE_5_REPORT](PHASE_5_REPORT.md)。
真实 PIT/历史成员/退市/公司行为和日历缺口仍保留。

### 正式提交与 Private 同步

- 功能提交：`05d190070ddd695c5fa1f72f316a601609c63db5`，
  `feat: add leak-safe ML and walk-forward validation`。
- 26文件的正式提交已从Phase4分支快进合并到main；两个分支普通原子Push成功，远端指针均为该SHA。
- 该次同步时仓库为 Private、默认分支为 main；Phase 3 为 65f1bca、Phase 2 为 ba26bea，完整历史保留。
- Push后两次未观察到自动运行，使用已有workflow_dispatch实测；
  [Phase4 CI 40602662692](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40602662692)
  的准确headSha为05d1900、conclusion=success；不混称为Push自动触发验证。

原独立审查材料保持不变，仅留本地。完整性SHA-256：

| 材料 | SHA-256 |
|---|---|
| REVIEW.md | 5b29608db44749a47ca17eb67ee0a5aafee6871a043078932c580cb318176c3e |
| probe_review.py | 4e4c7329db45a825a7b03a2362898de2dd8c05caec08079dbf1c780d798424c8 |
| results.json | e564223d42e094ec9a8ab5d52c4a8e480bd02aa9d5f6eb8d3e23af92f133f617 |

### 真实双平台 CI 与最终验收结论

已读取运行元数据、两个完整job日志并核对准确SHA05d1900，不把本机通过或旧Phase3结果当成Phase4 CI。

| 平台 | 实际结果 |
|---|---|
| Ubuntu / Python3.12.15 | 425 passed in65.61s；Ruff、76文件format、锁/配置/CLI、构建、sdist重建和双wheel干净安装全部通过 |
| Windows / Python3.12.10 | 425 passed in81.29s；同上全部通过 |

链接：[40602662692](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40602662692)。
元数据ci-result.json、job日志ci-ubuntu.log/ci-windows.log保存在work/phase4-closeout/。
本次没有CI失败或需删除/放松测试的情况，未改业务算法或锁版本。
上游Node20迁移及Ubuntu runner镜像变更提示保留，不影响本次结果；macOS仍未实机验证。

**Phase 4 最终验收通过，范围仅合成USD软件验证。** 原330测试/Phase0–3功能保留；
真实数据来源/PIT、历史成员/退市、公司行为/日历、未校准score、重叠标签相关性和真实Holdout治理限制不变。
没有通过本报告声称真实市场策略有效。Phase5只记录计划，不实施。

本节记录的是功能提交05d1900的实际CI。后续仅文档提交不改生产/测试/依赖；
仍须独立核对该最新SHA的Actions，不将本节结果冒充任意后续提交结果。
最终同步保留 Phase 2/3/4 的分支与原始历史；提交和实际 CI 证据如上。
