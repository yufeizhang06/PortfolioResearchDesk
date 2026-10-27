# Phase 3 — 因子研究方法与使用契约

范围：US / USD，日频或月频，**描述性的事后归因**。本模块不训练预测模型、不输出交易信号，
不把统计显著性、滚动 Beta 或高 R² 解释为可交易超额收益。原 Phase 1 的合成执行接口保持独立。

## 来源、频率与单位

- 官方来源：[Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)。
  使用美国 FF3 与 Mom 的 CSV ZIP，日频和月频分别下载；不混用国际、周频、年频或 FF5 数据。
- [FF3 定义](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library/f-f_factors.html)：
  `Mkt-RF` 已是市场超额收益；SMB 为小盘减大盘组合收益，HML 为价值减成长组合收益。
  RF 使用数据文件的同期收益，不将其再视为年化利率除以 252/12。
  官方说明 RF 截至 2024-05 源于 Ibbotson，2024-06 起源于 ICE BofA US 1-Month Treasury Bill Index。
- Carhart FF4 = FF3 + French `Mom`。
  [日频 Mom](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor_daily.html)
  与[月频 Mom](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor.html)
  均由规模与过去 2–12 月收益排序的六个价值加权组合构造，是赢家减输家因子；
  不等同于筛选模块中的单股过去涨幅。报告保存定义与实际下载端点。
- French 文件数值按**百分数**读取，一次除以 100 后内部统一为小数收益；1.25 → 0.0125。
  空值、`-99.99`、`-999` 先识别为缺失，再转换单位。RF 也做相同转换。
  转换通过精确的十进制指数移位完成，不继承调用方的精度、舍入或指数限制。
- 只读取第一个对应频率的表；不拼接月频文件后面的年度汇总。拒绝重复日期、错误日期、
  错列、频率不符、非有限数值与表内异常行。ZIP 不解压到文件系统，限定单个 CSV 和大小。
- 月频的 YYYYMM 统一标记为日历月末日期，仅作为**期间标签**，不是交易或发布时间。

French 历史可能修订。官方从 2025-01 数据发布起改用 CRSP CIZ；其月频收益由日收益复合，
现金分红按除息日再投资，与旧 FIZ 月末再投资约定不同。当前下载不能复原任意历史发布版本。
保存实际读取时间、来源 URL、原始响应 SHA-256、规范化快照及哈希，不宣称已验证历史 PIT。

## 股票收益与共同样本

`r[t] = P[t] / P[previous_period_end] - 1`，响应变量为 `y[t] = r[t] - RF[t]`。

- `return_basis="adjusted_close"`：使用供应商 Adj Close 比率，明确标记为供应商总收益代理。
  不再额外添加现金分红。没有独立证明其股息再投资、拆股与历史修订处理完全匹配 French。
- `return_basis="close"`：拒绝 `price_basis="provider_adjusted"`，不能按列名把调整价标成纯价格收益。
  `synthetic_raw/raw_declared` 按声明的未复权价格解释；`provider_ohlc` 仅标为 Close 列收益代理，
  不额外加入现金分红，并保留供应商调整规则未认证的警告。公司行为期间拒绝计算。
- 复用 Phase 2 native History 和质量检查。一个研究运行只分析一个明确身份的资产；
  实际行情可由同一个 Phase 2 `run_research()` 获取，并用 `asset_symbol` 选择。
- 日频用因子日期与观察到的价格日期并集确定相邻期间。缺失价格不会跨日桥接，
  缺失因子日期也不会把下一天变成多日股票收益。没有独立认证交易所日历，报告始终提示。
- 月频必须提供 `sessions_file`，每行一个有序且唯一的 ISO 交易日期，覆盖前一月和完整目标月份。
  使用清单中的各月最后 session 作为端点；缺少端点就剔除，不能偷偷用较早报价替代。
  清单及其来源权威性由用户负责，完整清单保存在质量快照中。真实验收清单来自 French 日频日期，
  只是对齐基准，不包装成独立的交易所日历认证。
  清单覆盖月份内存在报价日期却未列入 sessions 时，以 `CALENDAR_PRICE_CONFLICT` 拒绝，
  包括中间日期、月末与整月遗漏；不选较早报价继续回归。重复、乱序、带时间的 session 标签也拒绝。
- 同频、同日期、相同响应；FF3/FF4 一律使用四因子及 RF 都完整的交集。
  不为了 FF3 增加样本，不前填、不插值；所有剔除期间及原因留在 alignment.json。
- 配置 end 为不包含边界；价格数据应包含 start 之前的端点。多日区间错配明确剔除。
- R5：共享质量检查验证已知事件属于所声明的交易所本地日，并按 timestamp_basis 验证观测结束。
  时间标签矛盾以 SESSION_TIME_MISMATCH 在回归前明确拒绝；不把较晚下载误判为行情发生较晚。
  Yahoo 次日本地零点上界按夏令时处理，event_time 仍为 null；未知事件/来源/时区证据显示
  SESSION_TIME_UNVERIFIED，明确不可用于严格历史流程。这里只检查日线日期一致性，不认证实际收盘或历史发布版本。

## 回归和诊断

`y[t] = Alpha + beta_m*(Mkt-RF)[t] + beta_s*SMB[t] + beta_h*HML[t] (+ beta_u*Mom[t]) + error[t]`。

使用 [statsmodels OLS](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.OLS.html)，
显式加入截距并拒绝库内部隐式缺失删除。输出系数、SE、t、双侧 p、可配置置信区间、R²、
Adjusted R²、AIC、BIC、log likelihood、自由度、拟合值和残差。
Alpha 单位为“小数/观察期间”，Beta 无量纲；不自动外推年化 alpha。

- 默认 HC3：稳健于异方差，使用明确标注的近似 t 推断；**不修正序列相关**。
  可选 `nonrobust`：经典同方差且误差不相关的 SE。没有 HAC、聚类 SE 或多重检验校正。
- AIC/BIC 来自相同响应和样本的 Gaussian OLS likelihood，参数数包括截距；稳健协方差不改变
  OLS 拟合或该似然。报告 delta 定义为 FF4 − FF3；更低数值不是投资效果证明。
- 最少样本默认 20，且必须有正的残差自由度；小于 max(30,5×参数数) 时提示推断脆弱。
- 主动检查常数响应/因子、矩阵秩及标准化设计条件数。秩不足或条件数 > 1e8 阻断；
  条件数 > 30 或 VIF > 10 警告。VIF 用辅助最小二乘计算，避免直接求 X'X 放大条件数。
  [statsmodels 官方说明](https://www.statsmodels.org/stable/pitfalls.html)指出其广义逆不会自动拒绝奇异设计。
- 记录原始/标准化条件数、VIF、最大杠杆、残差均值/标准差、Durbin–Watson、Breusch–Pagan
  LM p 值及 Jarque–Bera p 值。它们是诊断，不是模型通过/有效性的认证。
- 数值零残差时保留可确定的系数，但 SE/t/p/CI、AIC/BIC 与有关残差统计置 null 并警告，
  避免无穷信息准则或虚假的显著性。非有限指标只以 null 输出；JSON 禁止 NaN/Infinity。
- 全样本统计失败仍可导出 `status="failed"` 的诊断包，并退出 2；缺少统计依赖则在取数前退出 2。

## 滚动窗口与历史可得性

Rolling Exposure 先取**截至窗口终点的最近 N 个名义期间**，再在该窗口内取共同有效样本。
缺失值不会从窗口之前补足观察数。每个窗口独立拟合 FF3/FF4，保存实际样本、窗口边界、哈希、
nobs、可得时间以及失败原因；预热阶段不足 N 个期间时不生成系数。

月频先在请求区间内建立完整日历月末网格，包含两边输入同时缺失的月份和区间边缘缺月。
Rolling 接口也补齐其可见起止月份之间的名义网格，兼容缺少 exclusions 的旧样本。
缺失月保留位置及诊断，绝不从更早月份补样本。日频仍使用来源/观测日期网格，无法推断两边
同时丢失的合法交易日，继续明确披露未认证交易日历；本轮不引入新的日历适配器。

修改未来观察值不能改变较早窗口。窗口结束日期也不代表 Beta 在历史当时已经可得：
本阶段真实因子 available_at 下界采用实际读取时间，收益采用端点及 History 版本的可得时间。
所有结果 `historical_signal_eligible=false`；`require_factor_signal_use()` 同时拒绝晚可得快照与
未验证发布版本。即使现时已经下载，也不把它作为历史实时可交易特征。

## 配置和报告

```text
prd config validate --kind factors --config configs/example_factors.toml
prd research run --config configs/example_factors.toml
prd research run --config configs/example_factors_real.toml
prd research run --config configs/example_factors_real.toml --offline
```

schema_version=3，与原有 0/1/2 配置隔离。路径相对 TOML 文件解析；默认随包样例完全离线。
`factor_source`：synthetic / french / local；local 要求 French 格式的 ff3_file/momentum_file，
其百分数口径及 expected_kind 由用户显式声明。价格来自 native price_file 或 Phase 2 research_config，
二者互斥。月频另需 sessions_file。示例 real 配置仅做日频，不自动猜测月末报价。

French 缓存复用不可变 SHA-256 快照及 SQLite，TTL 24 小时；`--allow-stale` 显式记录，
应用级 `--offline` 禁止请求。`uv --offline` 仅禁止依赖下载，不是行情请求开关。
整改后因子缓存使用 `french_us_v2`：v1 可能含受外部 Decimal 精度影响的值，保留旧文件但不复用。
首次需要按正常在线模式重新获取；只有旧 v1 缓存时应用级 offline 会明确失败。价格缓存不受影响。
超时和重试沿用现有有界策略，不使用合成数据或其他来源静默替代失败请求。

每个不可覆盖的运行目录保存价格/因子快照、收益、共同样本与剔除、质量、完整回归和滚动结果、
CSV、HTML、SVG/PNG。`run.json` 最后写入，包含业务状态、输入/代码/配置/依赖指纹、
运行时版本及产物 SHA-256；文件存在不等于统计成功。缺少完成标记表示导出未完成。

## 合成已知答案

随包 synthetic 数据有 1 个价格基点及 96 个收益期间，使用明确假定的工作日清单，非市场证据。
四列因子为 32 行循环的正交符号向量，尺度为 0.01/0.006/0.008/0.012；
RF=0.0001，Alpha=0.0002，Beta=(0.8,0.3,-0.2,0.5)，正交残差为 ±0.0003。
价格按 1+RF+线性项+残差递推，Adj Close=Close 且无公司行为。
因此可以独立手算系数、SSR、标准误、t/p/CI、R²、AIC/BIC 和等杠杆 HC3 标准误。
32 期间滚动窗口也有相同理论系数；测试同时检查未来扰动、缺失边界和数值异常。
