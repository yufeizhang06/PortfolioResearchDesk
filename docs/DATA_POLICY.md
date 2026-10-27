# Data Policy — Phase 2

日期：2026-10-27。范围为美国、USD、日频描述性研究；不执行真实交易。

## 来源、授权与覆盖

| 输入 | 实际来源 | 使用与覆盖限制 |
|---|---|---|
| 真实 OHLCV / Adj Close / 分红 / 拆股 | Yahoo，经第三方 yfinance | 不是交易所官方 API；历史修订、下架及退市覆盖不保证；使用者应核实 Yahoo 使用条款 |
| Market Universe | Nasdaq Trader 官方 nasdaqlisted.txt | 当前上市证券目录；排除 Test Issue、ETF、NextShares；仍可能含权证、单位等非普通股，不能称为 Nasdaq-100 或全美普通股全集 |
| CSV / Parquet | 用户提供的 native History 数据 | 必须提供来源、real/synthetic 标签、USD、时间及价格口径；格式验证不等于独立证明供应商声明 |
| 随包样例 | 项目自建固定 fixture | 全部为 synthetic，SYN_ 前缀；价格、日期和时间假设不代表市场证据 |

依据：[yfinance 项目说明](https://ranaroussi.github.io/yfinance/)、
[history 参数](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.history.html)、
[Nasdaq 目录](https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt)、
[官方字段解释](https://www.nasdaqtrader.com/Trader.aspx?id=SymbolDirDefs)。
yfinance 项目说明其不隶属于、未获 Yahoo 背书，工具面向研究，Yahoo 金融 API 数据限个人使用。
本项目不据此推定拥有公开再分发数据的许可；真实下载、缓存和研究输出默认仅本地保存。
Git 和发行包只包含程序、配置及自建合成 fixture，不包含本轮真实行情或目录快照。

当前 Market 入口满足“至少一个有明确来源的美国市场/指数入口”；**历史指数入口没有实现**。
缺失历史成分、退市、合并、更名及证券永久标识映射，因此幸存者偏差和身份历史问题没有解决。
目录的 USD 为研究范围假设，行情必须进一步以供应商 currency/exchange 元数据确认；
无法匹配时拒绝该资产，不猜测另一市场或币种。

## 时间与价格口径

`Observation` 保留 `session_date`、`event_time`、`observation_end`、`available_at`；
`History` 保留来源及版本、`retrieved_at`、`availability_basis`、`timestamp_basis`、`price_basis` 和限制。
所有时刻为带时区 UTC，交易所本地日日期单独保留。

- Yahoo 日线无法验证准确事件时刻，故 **event_time=null**，不伪造收盘时间。
- `observation_end` 使用交易所本地 session_date 次日 00:00 换算 UTC，明确为该日期的保守上界，
  不是准确收盘事件；当日尚未完成的观测会被质量检查隔离。
- 无法证明历史发布时间，故 **available_at=实际 retrieved_at**，
  `availability_basis=retrieved_snapshot`，不是 session_date 加固定一分钟。
  缓存命中保留原可得时间，不把读取缓存的时间改写成数据发布时间。
- 筛选只使用 `observation_end <= decision_at` 且 `available_at <= decision_at` 的输入；
  股票池本身也必须在该时点可得。未来扰动测试检查未来数据不能影响过去筛选。
- Phase 2 不产生订单或成交时间；Phase 1 原有 `decision_at < execution_at` 规则继续保留。

Yahoo 请求明确设置 `interval=1d, auto_adjust=false, back_adjust=false, repair=false,
actions=true, keepna=true, rounding=false, raise_errors=true`；end 日期为**不包含**边界。
OHLC 为 `provider_ohlc`，Adj Close 单独保留，分红/拆股另列。
关闭上述选项仍不能证明历史原始可成交价、split 前价格或修订前快照；不将其命名为可信 raw。
跨公司行为的筛选窗口需要复核并剔除，不默默混算价格收益与总收益。

**真实研究 History 不能传入 Phase 1 合成回测接口**。后者继续要求 raw cent prices、显式
session manifest 和无公司行为的合成数据。放开真实回测前仍需核实权威交易日历、成交时点、
公司行为、退市、价格与币种处理；当前报告始终标记 `historical_pit_verified=false`。

## 股票池与筛选

`UniverseSnapshot` 保存 universe_id、source、as_of、available_at、完整资产身份、synthetic、限制。
membership_type 为 `user_static`、`current_snapshot` 或 `point_in_time`；枚举值不代表已经验证 PIT。
`point_in_time_verified` 默认 false；保存的自选文件不能伪造已验证 PIT。
要求历史 PIT 时必须通过 `ensure_historical_use()`，当前目录一律阻断；不降级后继续声称无偏。
用户静态列表反映用户选择，不能证明历史无选择偏差。

三种模式通过同一服务输出同一快照契约；Custom + Screening、Market + Screening、
Market + Custom additions + Screening 均支持。没有随机抽样或静默截取前 N 只。
`max_assets` 是配置的请求预算，超出时要求用户显式缩小范围或调整预算。

筛选按 AND 组合：最少可用历史、价格动量 `P_t/P_(t-k)-1`、简单日收益样本标准差 `×sqrt(252)`、
平均 `close*volume`。成交额为日频近似，波动率年化用 252 约定，均非逐笔或权威日历计算。
每只资产保存 value_as_of、available_at、指标和入选/剔除理由；缺失或晚可得数据明确剔除。
当前不提供没有可靠发布日期的市值/行业/基本面筛选，也不实现标签、训练或 OOS 评价。

## 验证、失败与缓存

- OHLC/volume 缺失、非有限或非正价格、边界错误、重复、时间倒置、币种不符、异常公司行为、
  超过 100% 的相邻价格跳变会产生错误并隔离；重复的所有版本均隔离，不择优挑选。
- 零成交量、公司行为、未知 event_time、非历史 PIT 等明确警告；不前填、后填或用合成值补齐。
- 无权威交易日历时记录 `CALENDAR_UNVERIFIED`，不把周末/节假日猜测为合法缺口。
  用户提供 expected_sessions 时检查缺失日期；这验证输入清单一致性，不独立认证该清单的权威性。
- API 超时/连接失败/5xx 有界重试；429 尊重数字或 HTTP-date 的 Retry-After。
  超出短等待预算就停止，要求稍后重试，不为了快速完成而绕过限流。
  证券不存在、身份不符、空结果或 schema 变化明确报错；限流后停止其余未缓存请求。
- 多资产请求记录每只失败原因；仍有有效资产时报告 partial，无可用数据时 failed/退出 2。
  服务不保证外部接口持续可用，不使用其他来源或 synthetic 静默替换。
- SQLite 只负责查找；JSON 快照按 SHA-256 不可变保存，real/synthetic 分开命名空间。
  key 包括 Adapter/版本/价格参数、完整身份和日期；本地文件还含内容及 sidecar 指纹。
- TTL 默认 24 小时；过期默认重取或离线报错，`--allow-stale` 必须显式选择并被记录。
  `--refresh` 保留旧快照；损坏内容保留带 .corrupt 标识的证据后修复，正常读取遇损坏就失败。
- CSV 需固定列及同名 metadata JSON 校验；Parquet 内嵌版本元数据，十进制与 UTC 用文本精确保留。
  缺少声明的任意外部 CSV 不被自动推断为可信行情。数据文件与 sidecar 应作为一组保存。

## 当前验证边界

2026-10-27 已实际访问 Yahoo 和 Nasdaq 目录，验证 AAPL/MSFT 下载、三项缓存全命中、
真实 native CSV/Parquet 无损回放。测试使用固定本地数据及注入 transport，socket 被禁止，
不依赖 API Key、动态日期或外部服务；其中模拟响应只验证错误路径，不当成真实数据验证。
远端 GitHub Actions、Linux/macOS、完整市场批量、历史指数和退市覆盖尚未实测。
完整命令及结果见 `PHASE_2_REPORT.md`。
