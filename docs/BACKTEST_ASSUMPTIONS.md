# Phase 1 回测契约与手算

## 可用范围与 Schema

当前 CLI 数据源限定为包内自建 synthetic fixture。实现范围是完整纵向闭环，尚非 V1、真实市场
研究或 Walk-Forward ML。固定股票池在第一 session 开盘形成 `user_static` 快照；资产身份包含
market/exchange/symbol/currency，快照 as_of 为列表有效时点，不假设处理了历史更名或退市。

配置根字段为 schema_version=1、mode=backtest、market=US、data_source=synthetic、log_level。

| 表 | 必填字段与约束 |
|---|---|
| universe | source=custom、membership_type=user_static、symbols（SYN_ 资产数组，规范化去重） |
| account | base_currency=USD、initial_cash（正数，精确到分） |
| strategy | name=momentum_top_k、lookback_sessions、top_k（正整数；K 不超过股票数） |
| portfolio | max_position_weight∈(0,1]、cash_buffer∈[0,1] |
| execution | fill_policy=next_session_open、fractional_shares=false、commission_bps、fixed_fee、slippage_bps |

拒绝未知/缺失字段、错误类型、NaN/Infinity、CAD/FX、行业约束、真实供应商及未实现策略。
Decimal 参数可写十进制字符串或数值；初始现金/固定费精确到分。当前仅限 raw USD 分报价。

## 时间顺序与反泄漏

1. manifest 明确列出 session 的 UTC open/close，不用日期 + 1 天猜下一交易日，
   不把缺行推断成节假日；要求完整 panel，有任何缺行、重复、非法价格则阻断。
2. 每个 session 先处理上个收盘生成的订单，再在收盘后估值，最后形成新决策。
3. 约定日线 event_time=observation_end=21:00Z、available_at=21:01Z、decision_at=21:02Z。
   开盘价是模拟环境在 open_at 提供的 raw opening quote，tradable 是 fixture 对**开盘时**
   可交易性的声明。这是合成契约，不是供应商或真实交易所保证。
4. 日线 close/high/low/volume 不进入开盘执行决策。执行只使用原请求、现金/持仓、raw open、
   开盘 tradable 声明和预先配置费用；不把全天成交量当成开盘时已知的流动性。
5. 动量 `close[t]/close[t-L]-1` 仅看决策时已发生且已公开的最后 L+1 个日线；
   输入晚发布即阻断，不静默前填或后填。Signal 保存 observation_start/end、available_at、decision_at。
6. 强制 `observation_end <= available_at <= decision_at < execution_at`。
   订单请求按已知 close 确定；下一开盘只能缩减请求。批内先卖后买，按完整 AssetId 排序。
7. 最后一个 session 的新请求取消为 NO_NEXT_SESSION；终值为最后已知 close 市值加现金，
   不虚构未来成交，也不假设全部清仓。

已覆盖未来扰动、晚可得数据、同 session 成交拒绝、缺失 session 测试。尚无模型 fit、标签、CV、
Holdout；Phase 4 的 purge/embargo/折内拟合仍须后续实施。

## 组合、资金与费用

- Top-K 分数降序，完整 AssetId 打破平分；负动量也参与排名，没有隐式正收益过滤器。
- 每只入选资产 `w=min((1-cash_buffer)/K,max_position_weight)`，剩余权重保留现金；
  不为满仓破坏上限。未入选持仓目标零。
- 请求数量为 `floor(close_NAV*target_weight/known_close)` 与现有数量之差。
- 买入价 `ceil_cent(raw_open*(1+slippage_bps/10000))`；
  卖出价 `floor_cent(raw_open*(1-slippage_bps/10000))`，不利方向舍入到分。
- 每笔非零成交佣金 `ceil_cent(fixed_fee+quantity*fill_price*commission_bps/10000)`。
  滑点成本 `quantity*abs(fill_price-raw_open)` 已包含在成交价，不能再次扣现金。
- 现金更新 `cash -= signed_quantity*fill_price+commission`，买入数量为正、卖出为负。
  NAV 始终为现金加持仓 raw 市值。
- 二分搜索缩减买入数量，按实际费用扣除后的开盘 NAV 检查现金缓冲和单票上限。
  不借款、不做空、不放大原请求；不足一股留现金。
- 无买入开盘价/停牌则取消该订单；已有持仓缺少开盘价则取消整批，避免陈旧风险估值。
  开盘跳空导致现有约束在计划卖出后仍不可行时 fail closed，显式报错，不放宽限制。
- 成交后价格变化可能造成收盘权重漂移；报告警告，不声称持续满足目标上限。
- 引擎固定 Decimal 28 位上下文；无盘中撮合、流动性队列、税费、保证金或真实冲击模型。
  所有费用参数只是透明情景假设。

## 手算对照：example_handcheck.toml

100 USD、L=1、K=1、仓位上限 100%、现金缓冲 0、每笔佣金 1 USD，无 bps 和滑点。
正常配置另有费用、滑点和更保守约束。以下是已知答案，程序仍从成交和估值计算指标。

| Session | 收盘首名 | 本日执行 | 收盘现金 | 收盘持仓 | NAV |
|---|---|---|---:|---|---:|
| 01-02 | warmup | 无 | 100 | 无 | 100 |
| 01-03 | A | 生成买 A 9 股请求 | 100 | 无 | 100 |
| 01-04 | B | A 开盘 12，含费用只能买 8 股 | 3 | A×8，close=12 | 99 |
| 01-05 | C | 卖 A×8@12；买 B×4@22 | 9 | B×4，close=20 | 89 |
| 01-08 | A | 卖 B×4@20；买 C 请求 2 股，费用限制实际 1 股@44 | 43 | C×1，close=44 | 87 |
| 01-09 | B | 卖 C×1@44；买 A×5@15 | 10 | A×5，close=16 | 90 |

最后新请求卖 A/买 B 无下一 session，均取消。7 笔成交，佣金共 7；累计收益 -10%，
最大回撤 13%，raw 成交额合计 523。最终未实现持仓收益 5、已实现价差 -8、佣金 -7，
与资本损益 -10 一致。上述数字仅在测试/说明中作为手算断言，不在引擎中硬编码。

## 指标与局限性

- 累计收益 `ending_NAV/initial_NAV-1`；回撤包含初始资本峰值；period_return 是相邻收盘 NAV 比。
- traded_notional_over_initial_capital 为买卖两侧 raw 成交额合计/初始资本，不冒充年化单边换手率。
- 现金基准同初始资金、零利息、零交易，不是宽基 ETF 或真实可投资总回报基准。
- 6 个合成 session 不支持经济结论；年化收益/波动/Sharpe 不可用，不外推展示。
- 无公司行为：manifest 必须声明 corporate_actions=none；声明其他行为或 adjusted=true 则阻断。
  不能检测真实供应商漏报公司行为，所以 CLI 尚不开放真实数据源。
- USD-only；CAD、FX、行业约束、持久化 Paper Account、真实数据和历史 PIT 均未实现。

Decimal 的精确十进制和舍入语义参考
[Python 官方文档](https://docs.python.org/3.12/library/decimal.html)；其余为项目显式情景设计。
