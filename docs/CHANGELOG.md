# Changelog

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
