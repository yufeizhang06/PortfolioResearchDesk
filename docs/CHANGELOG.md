# Changelog

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
