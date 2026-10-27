# Phase 3 验收报告 — Factor Research & Diagnostics

日期：2026-10-27（America/Toronto）。版本：0.4.0。
分支：`codex/phase-3-factor-diagnostics`，基线 `ba26bea`。
**用户已正式批准 Phase 3 验收；R1–R5 全部 PASS。验收范围仅事后描述性因子研究，不是 PIT/OOS 交易策略认证。**

下方 270/298/330 测试、历史待验收状态及初次下载记录保留审查过程；当前验收与 Git/CI 收尾状态见末节。
本轮获授权 Commit、合并 main、普通 Push 及 CI 验证；尚未进入 Phase 4。

## 已实现与要求映射

| 要求 | 实现及证据 |
|---|---|
| FF3 / Carhart FF4 来源 | French 官方 US FF3 + Mom 日/月频 ZIP/CSV；真实访问与缓存回放 |
| 频率/单位/RF/Mom | 严格日期、百分数一次缩放、同期 RF、独立 Mom 定义；拒绝混频和年度汇总拼接 |
| 股票收益/对齐 | native History、简单收益、Adj Close 总收益代理或明确价格收益、月末 session 端点；无填补 |
| 公平模型比较 | 四因子/RF/股票收益共同完整样本，FF3/FF4 相同 sample_hash、响应和似然 |
| OLS 完整结果 | Alpha/Beta、SE、t/p、CI、R²/Adjusted R²、AIC/BIC、自由度、残差与拟合值 |
| Rolling Exposure | 尾随名义期间窗口、每窗独立共同样本、失败原因/边界/可得时间/哈希；未来扰动测试 |
| 历史可得性 | retrieved_snapshot，信号入口阻断，所有结果 historical_signal_eligible=false |
| 数据/统计诊断 | 重复/缺失/非有限/错频错位、样本不足、常数响应、秩/条件数/VIF、残差诊断与数值零残差 |
| 已知答案 | 96 个正交合成样本，独立公式验证系数、经典/HC3 SE、t/p/CI、R²、AIC/BIC 及滚动系数 |
| CLI / 报告 | prd research run、config validate --kind factors；JSON/CSV/HTML/SVG/PNG、输入与代码指纹 |
| 保留原成果 | 原 208 测试保留；新增 62 项参数化测试案例，总计 270 passed |

## 环境与依赖

Python 3.12.14 / uv 0.13.6；由 uv 解析并更新 pyproject.toml + uv.lock，不手改锁。
52 个锁定包；基础运行时依赖仍为空。新加可选 `factors` extra：

| 库 | 实际安装 | 安装元数据 Requires-Python |
|---|---|---|
| NumPy | 2.5.4 | >=3.12 |
| SciPy | 1.18.1 | >=3.12 |
| statsmodels | 0.15.0 | >=3.10 |
| matplotlib | 3.11.2 | >=3.11 |

查阅 statsmodels 官方安装、OLS、稳健协方差与 Pitfalls 文档，并以实际导入、回归和构建验证。
新环境位于忽略的 `work/phase3-clean-venv`，未修改系统 Python 或全局配置。

## 实际执行命令与结果

本机 PATH 没有 uv，使用 `work/bin/uv.exe`。任务环境：

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) 'work/uv-cache-phase3'
$env:UV_PROJECT_ENVIRONMENT = 'work/phase3-clean-venv'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
```

```text
uv sync --locked --extra data --extra factors --python .venv/Scripts/python.exe
uv lock --check --offline
uv run --locked --offline pytest -p pytest_socket -q --basetemp work/phase3-clean-tests -p no:cacheprovider
uv run --locked --offline ruff check .
uv run --locked --offline ruff format --check .
uv run --locked --offline prd --help
uv run --locked --offline prd --version
uv run --locked --offline prd config validate --kind factors --config configs/example_factors.toml
uv run --locked --offline prd research run --config configs/example_factors.toml
uv build --offline --no-build-isolation --out-dir dist/phase3
uv run --locked --offline python scripts/verify_distribution.py dist/phase3 --uv <本机uv绝对路径> --with-factors
```

- 全新锁定环境全量 **270 passed**；socket 被禁止，固定样例、无 API Key、无动态市场数据依赖。
- Ruff lint 和 format 检查通过，锁一致性通过。CLI/配置/离线示例与原 Phase 0–2 均验证。
- wheel + sdist 构建、sdist 离线重建、两个 wheel 各自独立干净 venv 安装通过。
  在源码外验证 Phase 0–2；基础安装缺少 factors extra 时退出 2 并解释；安装锁定 extra 后
  验证 Phase 3 理论系数和报告资源。没有依赖开发目录掩盖遗漏。
- SVG/PNG 已目视检查，数字、坐标、标签、图例可读；JSON/产物哈希和不可覆盖目录有测试。
- CI 配置已扩展 Phase 3，但**本阶段没有 Commit/Push，因此远端 CI 未执行**。
  Phase 2 的 Ubuntu/Windows 成功仍仅作为既有基线；Phase 3 不声称已跨平台实机通过。

## 真实接口验收（不是 Mock）

```text
uv run --locked --offline prd research run --config configs/example_factors_real.toml --run-id phase3-real-validation
uv run --locked --offline prd research run --config configs/example_factors_real.toml --offline
```

| 流程 | 实测结果 |
|---|---|
| French 日频 | FF3 日期 1926-07-01 至 2026-09-30，共 26,338 行；Mom 独立下载并按日期匹配 |
| French 月频 | FF3 月末标签 1926-07-31 至 2026-09-30，共 1,203 行；年度汇总未拼入 |
| AAPL 日频描述研究 | 2024-01-01 至 exclusive 2026-10-01，689 个共同有效收益；complete |
| AAPL 月频描述研究 | 同一区间 33 个共同有效月收益，24 期间滚动窗口 10 个成功；complete |
| 日频离线重放 | 因子与价格全部缓存命中，689 样本；与初次日频运行的共同样本一致 |

月频验收使用 French 日频日期作为显式 session 清单，包括前月端点；没有把月末标签当作实际交易日。
实际报告位于 Git 忽略目录：

- `outputs/factors/phase3-real-validation/`
- `outputs/factors/phase3-monthly-validation/`
- `outputs/factors/phase3-real-offline/`

完整本地摘要：`work/phase3-live-result.json`。真实输入/输出不进入 Git 或发行包。
原始响应 SHA-256：

| 输入 | SHA-256 |
|---|---|
| FF3 daily ZIP | 96c23b88e651cbfff3740a53f8225e59ee39893371e96385a1d8125ec2cd9c89 |
| Mom daily ZIP | e56d5bc845544e2993e77353b12c611cfce3149ef754f9b59fc67904ddadd369 |
| FF3 monthly ZIP | b03d39e4bb253dda0f14893db3b78e64b40b8d6549a0fc0fd4111dae84c98618 |
| Mom monthly ZIP | 27ed60e5b2caa9ea334a261cddfa864a9926f6bf45e9677c95dfd835c5abb315 |

## 验收中发现并修复的问题

- 真实请求初次失败：yfinance 当前返回惰性 Mapping，而旧 Adapter 限定 dict。
  改为接受 Mapping，仅读取身份必需键；新增测试确认不枚举 tradingPeriods 引发额外网络请求。
  币种/交易所/时区验证均保留，未用合成数据替代。上游 Pandas4Warning 仍记录，不隐藏或改依赖掩盖。
- 基础安装验证发现缺少统计 extra 被当作统计失败，随后版本元数据读取异常。
  将依赖检查前置到取数前，加入回归测试；缺少 extra 现在是清晰的用户错误。
- 离线独立安装首次因旧已安装依赖不在本轮缓存失败；创建完整全新锁定环境补全缓存后通过。
  没有修改锁定版本来绕过缓存问题。
- uv 对“缓存位于源码目录内”发出一般性提醒；sdist 显式 include 限制和发行包清单审查确认
  work、venv、缓存、真实数据和输出不被打包。跨文件系统 hardlink 回退复制不影响结果。

## 限制、差异和下一阶段依赖

1. 当前 French 历史是可修订的读取版本，没有历史公开时间或 PIT 发布档案证明；不能作历史信号。
2. 股票 Adj Close 是供应商总收益代理，未独立重建分红/拆股账本或认证与 French CIZ 的再投资规则一致。
   Close 口径只含价格变化。历史身份、退市、幸存者偏差和权威日历仍未解决。
3. 默认 HC3 不处理序列相关；无 HAC/聚类/多重检验校正。小样本 p 值、正态性及相关性诊断需谨慎解释。
4. 本阶段每次运行一个资产；热力图比较该资产的 FF3/FF4，未扩展为多资产批量图或行业归因。
5. 月频不自动猜 session 日历，必须显式提供；Warm-up 不足或窗口统计失败都可见，不填补系数。
6. 不新增 ML、标签、Walk-Forward、真实行情回测、FX 或持久账户。完整研究反泄漏认证仍待 Phase 4 等后续阶段。
7. 原始 PROJECT_PLAN 未改，SHA-256 保持
   `1f208c70b41aeaecfac45f1e38bcd2d3ff674f6eb1868352b45fd9eb40f752bb`。
8. main 和既有阶段分支指针保留；此阶段变更留在独立分支工作区，未暂存、Commit 或 Push。

后续 Phase 4 须用户另行授权。其前置条件包括 FeatureRow/LabelRow 的观测/可得/已知时间，
按全局日期划分、purge 和折内预处理；本阶段的因子诊断不能自动充当这些证明。

## 独立审查整改 — 等待第二次独立审查

### 审查材料与范围

完整报告实际位于 `work/phase3-independent-review/REVIEW.md`，不在仓库根目录。
已读取原始脚本 `review_math.py` / `review_boundaries.py` 和 JSON 证据，并在改动前重现反例。
原审查材料保留历史，不重写结论或更改其反例预期。此次仅修复 R1–R4，不重新开发 Phase 3。

生产代码只改三个文件：`factor_returns.py`、`factor_analysis.py`、`factor_data.py`。
版本仍为未正式验收的 0.4.0；pyproject.toml/uv.lock 本轮不增加或改变依赖。

### 逐项根因、修复与回归证据

| ID | 根因 | 最小修复 | 新测试与结果 |
|---|---|---|---|
| R1 / P1 | 由现存行重建时间轴，双边缺月消失，旧月份进入窗口 | returns 在请求范围建立完整月末网格并记录缺月；analysis 的 Rolling 也补齐可见起止月之间的网格 | `test_r1_missing_month_in_both_sources_keeps_nominal_windows`：24 月范围现在输出 13 个窗口；首窗结束 2022-12，2023-01 窗从 2022-02 开始且 nobs=10，与独立 QR 系数一致 |
| R2 / P1 | 清单内最大日期被无条件当作月末，未检测与报价的冲突 | 在清单覆盖月份内发现未列入的报价日期即 `CALENDAR_PRICE_CONFLICT`；不改用较早报价 | `test_r2_calendar_cannot_replace_existing_month_end_quote`：正确完整清单仍得到两个 10%；漏掉有报价的 1/31 明确拒绝，不再产生 5%/15.238% 的错误月收益 |
| R3 / P2 | Close 列选择未校验 price_basis，调整价被标为纯价格收益 | 拒绝 provider_adjusted + close；raw_declared/synthetic_raw 保持声明的价格收益；provider_ohlc 明确保留调整不确定性 | `test_r3_provider_adjusted_close_cannot_be_labelled_price_only`：调整价 99→99 仍能经 adjusted_close 得到 0；close 配置以 `PRICE_BASIS_CONFLICT` 拒绝；另验证原始 100→99 是 −1% |
| R4 / P2 | 除以 100 继承调用方 Decimal 精度/舍入/指数限制 | Decimal tuple 指数精确减 2，不进行受 context 影响的算术；因子缓存键升级 v2，保留但不读取旧 v1 值 | `test_r4_percent_normalization_is_independent_of_decimal_context`：precision 2/6/28 都得到 1.25%→0.0125；另验证极端 context、状态标志、同快照哈希和旧缓存隔离 |

全部新增用例在 `tests/test_factor_review_regressions.py`，共 **28 个参数化回归/边界案例**。
四个主测试先在修复前实际运行得到 **4 failed**，再在修复后运行得到 **4 passed**，没有改其预期。
证据：`work/phase3-remediation/red-tests.log` / `green-tests.log`。

额外边界包括：前后边界缺月、旧 AlignedSample 没有缺月 exclusion、未来扰动、重复/乱序/
datetime session、清单漏中间日期或整月、重复及时间不可用的月末报价、跨月区间错位、
不同复权/收益口径、缺失 Adj Close 不回退，以及 CLI 错误退出 2 且不产生成功标记。

### 数学实现与既有测试保持

改动前保存源码哈希；核对 `_libraries`、`_finite`、`require_factor_dependencies`、`fit_ols`、
`compare_models` 五个函数与 **19 个原有测试文件**均保持原样。
只在 Rolling 调度处加入月频网格，未改 OLS 求解、经典/HC3 协方差或统计量实现。

复用原独立审查脚本中未改动的有理数、QR、t 密度积分与求根参考函数，避开如今应被阻断的
旧错误调用路径。对合成及整改前/后的真实日/月样本共 **20 组 FF3/FF4 × 协方差组合**复核通过。
实现和哈希证据：`work/phase3-remediation/verify_references.py` / `references.json`。

### 本轮实际验证

```text
uv sync --locked --extra data --extra factors --offline
uv lock --check --offline
uv run --locked --offline pytest -p pytest_socket -q --basetemp work/phase3-remediation-final-tests -p no:cacheprovider
uv run --locked --offline ruff check .
uv run --locked --offline ruff format --check .
uv run --locked --offline python -B work/phase3-remediation/verify_references.py
uv run --locked --offline prd config validate --kind factors --config configs/example_factors.toml
uv run --locked --offline prd research run --config configs/example_factors.toml --run-id phase3-remediation-synthetic
uv run --locked --offline prd research run --config configs/example_factors_real.toml --offline --run-id phase3-remediation-real-cli
uv build --offline --no-build-isolation --out-dir dist/phase3-remediation
uv run --locked --offline python scripts/verify_distribution.py dist/phase3-remediation --uv <本机uv绝对路径> --with-factors
```

使用上文同一锁定环境与本地 uv；固定 Run ID 已存在，复验请换新 ID。

- **298 passed**，保留全部原 270 个测试；Ruff lint/format、锁文件和锁定离线同步通过。
- wheel/sdist、sdist 重建、两个 wheel 各自干净 venv 的源码外 Phase 0–3 命令与报告验证通过。
- 扩展精度测试首次有 2 个失败源于测试继承先前 Decimal sticky flags；明确清空测量前状态，
  保持“解析不触发舍入”的断言，再新增“不改已有 flags”用例后通过。没有删除测试或放宽预期。
  初次扩展运行日志 `full-tests.log` 与后续 `full-tests-2.log` / `final-tests.log` 均保留。

真实来源本轮重新获取，而非把 Mock 当实测：

| 项目 | 本轮结果 |
|---|---|
| Yahoo AAPL | 新价格缓存首次 miss；709 行，质量接受 709 行，原始数据仅留本地 |
| French 日频/月频 | v2 缓存各首次 miss，四份原始响应 SHA-256 与首轮记录一致 |
| 日频共同样本 | 689，564 个窗口，0 个失败窗口；complete |
| 月频共同样本 | 33，10 个窗口，0 个失败窗口；complete |
| 日频离线回放 | 因子缓存命中、本地原始价格读取；共同样本及快照与本轮在线结果完全一致 |
| 真实月末冲突 | 从日历删掉仍有报价的 2024-01-31，明确拒绝，不输出错误收益 |

执行入口及摘要：`work/phase3-remediation/validate_real.py` / `real-results.json`。
报告在 `outputs/factors/phase3-remediation-daily/`、`phase3-remediation-monthly/`、
`phase3-remediation-offline/`。默认示例和真实配置的 CLI 也分别完成，独立于服务调用。
上游 yfinance Pandas4Warning 仍记录，未隐藏或调整锁定依赖掩盖。

### 兼容影响与剩余风险

- v1 因子缓存可能含旧精度造成的值，不能从响应哈希修复，因此旧文件保留但隔离；
  首次需正常在线获取 v2，然后才可离线回放。价格缓存、旧报告及审查材料不删除。
- provider_adjusted + close 从不可靠标注改为明确拒绝；用户须选择有效 adjusted_close
  代理或明确声明的未调整价格输入，不静默转换。
- 月频清单依然是用户声明的日历，系统检测报价冲突但不能独立认证其权威性或完整性。
  如果清单和报价同时遗漏某个交易日，端点真实性仍需外部证据；不能因此声称可信 PIT。
- 日频不猜测缺失于双方数据中的交易日，权威日历仍未提供。本轮未新增市场日历适配器。
- 历史发布版本、Adj Close 与 French CIZ 再投资口径、公司行为账本、退市/PIT 覆盖仍受原限制。
  HC3 不修正序列相关，无 HAC、聚类或多重检验校正。
- Phase 3 正式验收继续暂缓，等待用户安排第二次独立审查；本地通过不等于远端 CI 通过。
  未 Commit、Push、触发远端 CI 或进入 Phase 4。

## 第二次审查 R5 整改 — 等待专项独立复核

### 原始证据、根因与范围

已读取 `work/phase3-second-review/REVIEW.md`、`timestamp_e2e.py`、原始 good/bad native CSV、
CLI 配置及 `timestamp-case/results.json`。原材料保持不变。第二次审查已确认 R1–R4 PASS，
本轮仅处理新增 R5 / P2，没有重开 Phase 3 或进入 Phase 4。

根因：原质量层只检查 event_time ≤ observation_end ≤ available_at，收益按 session_date 分桶；
一个 7/29 的事件被标成 6/30，晚到的下载时间使旧顺序检查合法，却没有证明它属于 6 月。
问题出在观测期间标签，不是 RF、OLS 或 Rolling 的数学公式。

生产改动仅 `data_contracts.py` 和 `factor_returns.py`：

| 字段/契约 | 修复后的含义与处理 |
|---|---|
| session_date | 支持的美国交易所本地日标签；已知事件使用 America/New_York 的半开本地日区间核对 |
| event_time | 已知的真实行情事件时刻；不得属于另一个本地日，不能拿下载时间代替 |
| observation_end | explicit_source_timestamps 在本地日内或恰好次日零点；exchange_local_date_upper_bound 必须恰为次日本地零点 |
| retrieved_at | 当前 History 版本的实际下载时间；合法历史数据允许延后下载，不改写事件标签 |
| available_at | 原可用时间声明保留；retrieved_snapshot 仍等于实际下载，不伪造历史公开时间 |
| 明确矛盾 | SESSION_TIME_MISMATCH，质量层隔离；因子入口退出 2，回归/滚动/成功报告之前停止 |
| 证据不足 | SESSION_TIME_UNVERIFIED，机器质量记录及收益/CLI/HTML 警告明确仅描述性且不可用于严格历史流程；因子历史信号入口仍阻断 |

不以 UTC 日期相等代替本地日，不猜固定 UTC 偏移；夏令时的 23/25 小时日期与合法跨 UTC 日均保留。
现有 ZoneInfo 无数据库、交易所未知或 timestamp_basis 不支持时明确降级；即使缺数据库，
超过一个 UTC 日期的已知日线矛盾仍拒绝。没有引入新依赖、改 schema、改缓存或替换输入。

### 回归测试与原 CLI 复验

新增 `tests/test_session_time_alignment.py`，共 **32 个参数化案例**：

- 日频/月频已知未来事件错标，质量隔离且收益入口报错；公开 native CSV→CLI 两频率均退出 2，无成功目录。
- 同 UTC 日但不同本地日拒绝；不同 UTC 日但同本地日接受；半开午夜边界、闰日、年末、夏令时正常。
- Yahoo 未知事件保留 null，冬/夏以及 23/25 小时本地日期的观测上界正常；错误夏令时偏移及跨月结束时间拒绝。
- declared 与 retrieved_snapshot 的晚下载均保留合法历史收益；未知事件、契约、交易所或数据库显示明确限制。
- 五种支持的美国交易所身份；无 IANA 数据仍能拒绝已知跨月矛盾。
- 分析人员显式隔离后重放：日频缺损不跨日补齐，月频缺月不扩窗。日28/月13个窗口与独立 QR 系数一致，
  日13/月1个历史完整窗口不受未来响应扰动影响。隔离由调用方明确完成，产品不静默修复或重标日期。

四个主要反例在未修复源码上先得到 **4 failed**；随后使用当前最终测试文件对保存的未修复 wheel
再做同一文件的旧/新源码对照，得到 **4 failed / 4 passed**，测试文件哈希在两次执行间相同。
证据：`work/phase3-r5/red-final.log`、`counterfactual.json`、`counterfactual-before.log`、`counterfactual-after.log`。

原第二次审查的配置和输入也重新通过公开 CLI 执行：正确 good 输入退出 0、24 月且零隔离；
bad 输入退出 2、隔离 1 条，stderr 明确 SESSION_TIME_MISMATCH，stdout 为空且无成功报告。
没有重写原 `timestamp_e2e.py` 来改变其历史发现。

### 本轮实际验证与证据

Python 3.12.14 / uv 0.13.6，仍使用本机 `work/bin/uv.exe` 及 `work/phase3-clean-venv`；
UV_CACHE_DIR 为 `work/uv-cache-phase3`，pytest 禁用自动插件并显式加载 pytest_socket。

```text
uv sync --locked --extra data --extra factors --offline
uv run --locked --offline --no-sync pytest -p pytest_socket -q --basetemp work/phase3-r5-final-tests -p no:cacheprovider
uv run --locked --offline --no-sync ruff check .
uv run --locked --offline --no-sync ruff format --check .
uv lock --check --offline
uv run --locked --offline --no-sync prd --help
uv run --locked --offline --no-sync prd config validate --kind factors --config configs/example_factors.toml
uv run --locked --offline --no-sync python -B work/phase3-r5/counterfactual.py
uv run --locked --offline --no-sync python -B work/phase3-r5/verify_r5.py
uv build --offline --no-build-isolation --out-dir work/phase3-r5/preflight-dist
uv run --locked --offline --no-sync python -B scripts/verify_distribution.py work/phase3-r5/preflight-dist --uv <本机uv绝对路径> --with-factors
```

- **330 passed in 9.52s**，原 298 项全部保留并通过；Ruff、63 个文件格式、锁一致性及离线锁定同步通过。
- fit_ols、compare_models、rolling_exposures 及原 **20 个测试文件**与本轮基线哈希一致。
  R1–R4 的整个新增测试文件也未修改；没有删除用例或放宽预期。
- 复用未改动的独立有理数求解、QR、显式协方差、t 密度积分参考函数，20 组 FF3/FF4 × classic/HC3 复核通过。
- socket 禁用后的真实缓存重放：709 条 Yahoo 报价零隔离；日689样本/564窗，月33样本/10窗，零失败。
  共同样本哈希及完整回归分析与整改前报告一致；新未知事件警告可见。这是现有快照验证，**没有重新在线下载**。
- wheel/sdist、sdist 离线重建、两个 wheel 的干净环境安装和源码外 Phase 0–3 CLI/资源验证通过。
  最终文档整合后的发行包与源码清单另记录在 `work/phase3-r5/final-audit.json`；不提交发行物或真实数据。
- 首次新增测试运行 25 passed/1 failed，原因是测试先构造 retrieved_snapshot 再改 declared，提前触发已有构造约束。
  修正为直接按 declared 构造输入，保留所有断言；日志 `green-tests.log` 保留。后续全量324及最终330均通过。

完整执行证据保存在 Git 忽略的 `work/phase3-r5/`：`final-tests.log`、`quality.log`、`verification.json`、
`original-cli-*-stdout.txt` / `stderr.txt`、`distribution-preflight.log` 和最终构建/安装日志。

### 限制与验收状态

这里只验证来源声明的日线时间一致性，不认证真实收盘时刻、合法交易时段/日历、供应商真实性或历史公开版本。
无法发现把价格与全部时间一起篡改成自洽输入的情况；用户声明仍不等同于外部证据。
未知事件/来源/数据库的描述性降级不能用于严格历史决策；真实 History 与本阶段因子仍无 PIT/OOS 保证。
French 修订版本、Adj Close 与 CIZ 再投资、公司行为、退市与身份覆盖、HC3 不修正序列相关等限制全部保留。

版本仍为未验收的 0.4.0；开发分支 `codex/phase-3-factor-diagnostics`，main 保持原样。
未 Commit、Push、触发远端 CI 或进入 Phase 4。**R5 本地整改完成，停止等待专项独立复核；不是自行通过正式验收。**

## 最终独立复核与用户验收 — 2026-10-27

用户正式批准 Phase 3 在**事后描述性因子研究**范围通过验收，并授权本阶段文档收尾、正式 Commit、
合并 main、现有 Private 仓库普通 Push 和 Ubuntu/Windows CI 检查及必要修复。Phase 4 未获授权。
前文待审查及未提交状态均为历史记录，不代表本节之后的当前状态。

| 类别 | 当前结论 |
|---|---|
| 已实现 | US FF3/Carhart FF4 日/月来源、单位/RF、同样本比较、OLS/HC3 完整统计、名义尾随窗口、诊断与统一 CLI/报告 |
| 已通过验证 | R1–R5 全部 PASS；最终独立复核重跑330项测试，21,538个独立时间组合、26组窗口QR对照及晚下载/证据不足/CLI传播验证通过 |
| 实际源码 | 当前 Python 文件与最终 R5 复审版发行包逐字节一致；收尾不改回归、时间校验或交易逻辑 |
| Git/CI 收尾 | 功能提交b929b8f、CI修复139d17f均已合并main并普通Push；真实Ubuntu/Windows CI通过，见末节 |
| Known Limitations | 无历史 PIT/公开版本、权威交易日历或退市覆盖认证；Adj Close 为总收益代理，CIZ/公司行为账本等价未认证；HC3不修正序列相关 |

验收不包含真实数据交易回测、策略盈利能力或可信 OOS 声明。来源/事件/时区证据不足继续明确限制为描述性，
historical_signal_eligible=false；下载时间不能伪装成历史公开时间。

最终独立报告与证据仅留本地 `work/phase3-r5-final-review/`，不上传真实输入、缓存或完整工作目录。
公开可复现的正常/边界/异常路径由正式测试和合成 fixture 保留。
收尾按 `.gitattributes` 将新增 FF3/Mom 合成 CSV 及其新增 metadata JSON 统一 LF；独立解析确认数值/JSON含义不变，
避免 Git checkout 的换行规范改变本地输入指纹。原始 PROJECT_PLAN 保持不变。

提交前本轮再次执行：Python3.12.14/uv0.13.6、锁定data/factors环境、**330 passed in 9.45s**，
Ruff lint/63文件format、锁一致性、wheel/sdist、sdist重建、双wheel干净安装与源码外Phase0–3验证通过。
37个候选文件敏感模式检查未检出；原有业务Python及测试50文件保持最终复审版本。
候选/索引清单和命令日志仅在本地 `work/phase3-closeout/`；远端CI通过后另补真实运行链接。

### 首次真实 Phase 3 CI 与冷缓存安装修复

功能提交 `b929b8f29ca2e0126112241c907dc0b44ddb11a0` 已快进合并 main，并与开发分支普通 Push 至原 Private 仓库。
Push 后未观察到自动运行；显式 workflow_dispatch 的真实运行：
https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40597082932。

首次两平台均在发行包干净安装步骤失败；此前 Ubuntu 330 passed in 19.35s，Windows 330 passed in 26.05s，
Ruff、CLI与构建均通过。失败不是因子数学或时间校验：锁定sync按wheel URL下载了依赖，
随后导出的requirements按包名重新解析，冷缓存没有对应registry索引元数据，离线解析报contourpy未缓存。
早先本地长期使用的缓存包含这些额外元数据，掩盖了此环境差异。保留失败日志，不把首次运行重写为成功。

修复仅限 `scripts/verify_distribution.py`：在临时环境直接运行锁定离线sync安装factors依赖，
`--no-install-project --inexact`保留刚安装的wheel；额外通过隔离Python断言包位于临时venv且具有wheel来源元数据，
防止源码editable安装掩盖问题。没有删除验证步骤、改测试预期或变更锁定版本。
参考 [uv sync/partial installation](https://docs.astral.sh/uv/concepts/projects/sync/) 的官方语义。

以全新任务专用缓存重新锁定安装后，旧验证流程实际失败于同一contourpy错误；同一冷缓存下修复流程完整通过
sdist重建、两个wheel的干净安装及源码外Phase0–3检查，依然全部离线。证据：
`work/phase3-closeout/cold-sync.log`、`cold-before.log`、`cold-after.log`。远端修复结果继续按实际运行补记。

### 修复后真实 CI 通过与最终同步

- 功能 Commit：`b929b8f29ca2e0126112241c907dc0b44ddb11a0`，
  `feat: implement and validate factor research engine`。
- CI 安装修复 Commit：`139d17f2feb0ebce537399e3c0f145a123db79a6`，
  `fix: reuse locked wheel cache for isolated factor checks`。
- 两者已通过保留完整历史的快进合并进入 main；main及Phase3分支已普通原子Push，原Phase2分支仍为ba26bea。
- 仓库仍为Private，未Force Push、改可见性、创建Release或进入Phase4。
- 修复后的真实运行：[40597881595](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40597881595)，
  headRevision精确为139d17f，conclusion=success。

| 平台 | 实际结果 |
|---|---|
| Ubuntu / Python3.12.15 | 330 passed in 18.65s；Ruff lint/format、配置/CLI/合成研究、构建、sdist重建、双wheel干净安装通过 |
| Windows / Python3.12.10 | 330 passed in 26.71s；同上全部通过 |

本轮Push未观察到自动运行，使用现有workflow_dispatch入口实测；不把人工调度混称为Push自动触发已验证。
首次失败运行40597082932及其日志保留。后续只记录验收与Git/CI文档的提交，其当前状态应查询对应SHA的Actions，
不把本节139d17f的结果冒充任意后续提交的结果。收尾结束时会再次核对最新提交CI和本地/远程main一致。

验收后限制保持：本模块仅事后描述性因子归因，无PIT发布档案/可信OOS策略认证；未知事件/来源/时区证据明确降级，
Adj Close/公司行为、权威日历、退市与身份覆盖等第三方数据限制仍未解决。Phase4须用户另行明确授权。
