# Phase 4 — 模型与时间序列验证

仅适用于 synthetic USD 实现验证。真实来源没有历史 PIT、成员/退市、权威日历及公司行为保证，
Phase 4 的配置和数据入口显式拒绝真实数据，不声称完成可信真实策略 OOS。
Phase 3 French 因子和事后回归结果不进入特征。

## 特征、标签与时间

`ml_data.py` 的确定性整数生成器创建 3 资产 × 320 个显式 weekday sessions。
日期/固定 UTC 开收盘只是假设，并非交易所日历（包含实际节假日，UTC 时间不随 DST 变化）。
原始 OHLC 为美元分、无拆股/股息；声明 `synthetic_v1`，无真实市场输入。
输入快照和生成器源码随报告/发行包留存，外部 Decimal context 不影响生成和计算。

FeatureRow 保留资产、decision_at、observation_start/end、available_at、固定版本和有序数值。
60 个 session 暖身之后输出：过去 5/20/60 日简单价格收益，20/60 日收益样本标准差（不年化），
`log1p(mean(close*volume, 20))`，个股 20 日收益减固定三资产收益均值。
最后一个市场代理依赖同一固定面板所有资产；available_at 取全部依赖最大值。
每行必须 `observation_start <= observation_end <= available_at <= decision_at`；
晚可得数据拒绝，不后移/回填。没有全局标准化、未来移位、财报或行业特征。

默认 h=5：决策 t 收盘后 2 分钟；标签从 t+1 开盘至 t+h+1 开盘，
`forward_return = open[t+h+1]/open[t+1]-1`，分类 target 为收益严格大于 0。
保留 label_start/end/known_at；保守使用两个端点日线的 available_at 作为 known_at，
即使开盘早已发生，也等该日数据声明可用后才可训练。
端点无开盘、停牌、零成交量或尾部不足时 label=None，预测仍保留并记录指标排除原因。
这不是总收益标签，也不是扣费后的实际成交收益；整股、成本和缩单另由回测引擎计算。

## 时序划分与 Purge

全部资产按全局 decision 日期分组，绝不随机打散或对展平股票行使用 TimeSeriesSplit。
默认 260 个有效特征日期中，前 220 日是开发区，最后 40 日是最终 Holdout。
开发区初始 100 日期候选训练，之后每 20 日期一个验证折，共 6 折。
`max_train_dates=0` 为 expanding；正数限制最近候选训练日期，实现 rolling。
选用窗口均为 purge **之前**的候选日期数，实际训练行数写入审计。

每折保留最晚 `gap_dates + embargo_dates` 个候选训练日期作为空档。
随后按标签区间/known_at 再 purge：标签必须结束且已知于验证首日 UTC 零点**之前**。
这比允许在验证首日收盘时拟合更保守，不让验证首日任何行情结果影响训练。
任一资产标签不合法就删除该日期所有资产，避免不透明的面板残缺。
UTC 零点边界只适用本 synthetic UTC session 契约，不应直接用于真实市场。

此处 embargo 是额外的前置安全缓冲，**不是**双向 CV 中测试窗后再剔除未来训练的机制。
本系统只训练过去，测试之后的数据从不进入同一折训练，因此无须双向 post-test embargo。
前一验证折可在后续折成为训练资料，但其标签结束/已知时间仍须逐折满足相同条件。
Gap 不能替代 interval purge；未知标签不参与训练。

## 模型、Pipeline 与嵌套调参

每个模型都使用同一折内 Pipeline：训练中位数 Imputer → StandardScaler →
VarianceThreshold（删除训练内常量特征）→ estimator。当前固定合成特征完整；Imputer 供
Pipeline 的明确缺失处理契约使用，不允许通过填补价格、标签或未知时点来伪造历史数据。
Lasso 本身的 L1 正则可以将系数置零；没有使用全样本的重要性或筛选结果。
这里没有额外的 SelectFromModel(Lasso) 特征筛选器：显式筛选步骤是 VarianceThreshold，
Lasso 是 Pipeline 末端连续收益估计器，其系数收缩/置零和 alpha 调参也只在训练折内发生。

| 模型 | 目标/输出 | 固定小网格 |
|---|---|---|
| Dummy prior | 训练期正类比例，朴素分类基线 | 无 |
| Logistic Regression | 分类/未校准 class score | C = 0.1、1 |
| Lasso | 连续 forward price return；分类阈值 0 | alpha = 0.0001、0.001 |
| Random Forest | 分类/未校准 class score | depth = 2、4；40 棵；leaf >= 5 |
| XGBoost CPU hist | 分类/未校准 class score | depth = 1、2；40 轮；learning_rate=0.05 |

在外层**已经 purge 的训练日期**内部，以 TimeSeriesSplit 创建 2 个、各 15 日期的内层验证窗；
再按相同规则 buffer/purge，每个参数候选每个内折重新 fit 完整 Pipeline。
目标固定为内折平均 F1，平手取网格首项。外层验证值不参与参数选择。
模型用 seed=42、单线程 CPU；记录实际参数、筛选 mask、填补统计、Scaler 均值/尺度、
线性系数/截距或树重要性。分类训练只有一类时明确使用 prior fallback；不伪造树拟合。
全部特征成为常数等拟合失败明确阻断；不静默回退到未来训练资料。

外层开发预测合并后以 pooled F1 选择模型，平手按配置顺序。开发标签若跨到最终 Holdout
首日或更晚才可知，排除其开发评价，防止选择模型时偷看 Holdout。
最后只在 Holdout 前合法训练集内调参一次，冻结全部模型参数、winner、特征、阈值与调仓规则，
记录 plan_hash，然后每模型 fit 一次预测整个 Holdout。Holdout 期间不重训、不挑 winner。
全部预声明模型都展示；不能根据 Holdout 排名事后改写 selected_model。

Hash 证明保存内容可校验，不强制研究者真的事先登记，也不能阻止反复试验偏差。
“冻结”指当前运行内的程序隔离；此合成 Holdout 已反复运行和查看作软件测试，
不能把它描述为从未参与过开发观察的一次性真实研究测试集。
本合成样例可重复运行作软件测试；未来真实研究须独立冻结方案/数据和一次性评估记录，
不能把此样例反复调试称作未触碰真实测试集的证据。

## 指标与模拟组合

每折、开发整体和最终 Holdout 输出 Accuracy、Precision、Recall、F1、ROC-AUC、混淆矩阵，
并保留样本数、正类数、阈值、预测覆盖和排除。类别预测使用 score > 阈值（分类 0.5/Lasso 0）。
分母为零的 Precision/Recall/F1=0；只有一类标签时 AUC=null 并附原因。
重叠收益标签与序列相关使行不独立，不给 IID 显著性、置信区间或“稳定胜率”声明。
未校准 predict_proba 不称为真实上涨概率，Lasso 分数不是概率。

各 stage 独立从 1000 USD 现金起步；所有模型、Momentum 使用 Top-2 等权风险约束；
Equal-weight/Buy-and-Hold 使用全部三资产，Cash 零利息。相同面板、阶段日期和默认成本：
单票上限 60%、现金缓冲 10%、5bps 佣金 + 0.10 USD 固定费、10bps 不利滑点。
每 h=5 个有效 OOS 日期调仓，Buy-and-Hold 只在阶段第一决策日买入。
ML score 用于资产排名（包括负分）；分类阈值仅用于分类评价，没有事后调仓阈值优化。
标签持有期与默认调仓周期一致；尾部不足完整标签仍可模拟持仓，但指标排除。

`run_backtest(..., signal_provider=...)` 复用原组合、收盘整股请求、下一显式开盘执行、
费用、滑点、现金、缩单和 NAV。provider None=保持；空 tuple=现金；完整资产 Signals=调仓。
不同日期、资产不全或晚可得信号拒绝。原不传 provider 的 Phase 1 动量行为保持。
报告开发和 Holdout 分离，不把开发期选择后的表现合并成独立真实 OOS。
成本另算 0 倍/2 倍情景。末尾标记持仓，不强平；停牌/缺开盘保留原执行器取消语义。
无年化、Sharpe、行业限制、CAD/FX 或真实订单。

## 审计与边界

`prd ml run` 保存不可覆盖目录，JSON、CSV、HTML；run.json 最后写出，逐文件 SHA-256。
保存输入快照、FeatureRow/LabelRow、每个内/外折索引/时间、模型参数、训练统计、预测、
指标、冻结方案、每策略订单/成交/持仓/NAV、成本情景以及代码、配置、数据和依赖指纹。
源码安装可读取 uv.lock；独立 wheel 缺该源文件时 dependency_lock_hash=null，
实际运行的依赖版本仍记录，不能虚构 lock 哈希。
正式测试禁止 sockets，不依赖 API Key、动态时间或市场网络。报告生成时间/随机 Run ID 仅元数据。

检测器验证契约和固定构造器，不可能从任意数值推断“该值其实抄自明天”。故意使用未来
observation_end/available_at 会拒绝；把未来值和全部来源时间一起伪造成自洽输入则需要外部
PIT 证据和独立代码审查。这一限制不能以测试通过取代。

最终验收补充的六项测试不改模型或特征：五模型分别翻转外层验证标签，验证内层试验、选参、
训练统计和分数保持不变；全五模型流程同时扰动 Holdout 特征并翻转标签，验证开发指标、
冻结方案、内层调参和最终拟合不变，而 Holdout 评价确实改变。它们补充既有审查的价格扰动证据。

官方参考（2026-10-27 核查；版本以 lock 和安装元数据为准）：

- [scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
- [scikit-learn 数据泄漏与 Pipeline](https://scikit-learn.org/stable/common_pitfalls.html)
- [Lasso 目标函数](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Lasso.html)
- [scikit-learn 安装兼容说明](https://scikit-learn.org/stable/install.html)
- [XGBoost 官方安装](https://xgboost.readthedocs.io/en/stable/install.html)
