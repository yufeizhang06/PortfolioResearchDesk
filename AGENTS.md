# PortfolioResearchDesk 协作约定

## 当前范围

- 2026-10-28：用户原则批准 Phase 5 最终验收，授权证据核实、完整3000 CAD演示、必要缺口测试、
  正式Commit、安全快进合并main、普通Private Push及准确SHA的Ubuntu/Windows CI检查与实际问题修复。
- Phase 5 分支 `codex/phase-5-cad-paper`，稳定基线 `0e4ca9677ed2e53dd2641b0f49157de88030aaa8`，保留该分支。
- 仅做Phase5收尾，不进入Phase6、不创建正式Release、不Force Push、不改变可见性或其他仓库。
- 已有608本地测试与独立修复复验通过；当前46生产源码/13审查材料hash已核对一致，不重复完整独立审查。
- 本轮真实CI及Git状态以PHASE_5_REPORT后续实际记录为准，不能挪用Phase4结果。
- 真实PIT/OOS及完整公司行为不在认证范围。下列Phase4授权/停止范围为历史上下文。

- Phase 0–4 已完成技术验收；Phase 3 R1–R5仅为事后描述性因子研究，Phase 4仅为合成USD软件验证，均不是可信真实PIT/OOS交易策略认证。
- Private 仓库为 yufeizhang06/PortfolioResearchDesk；Phase 3 已合并上传 main，Ubuntu/Windows 各330测试及构建安装 CI 已实测通过。
- Phase 4功能提交05d1900已快进合并main并普通Push；真实CI40602662692在该SHA两平台各425测试及构建安装通过。
- 当前用户已授权 Phase 4 最终验收、审查证据核实、必要针对性测试、正式 Commit、安全合并 main、普通 Push 及 Ubuntu/Windows CI 检查和真实问题修复。
- Phase 4开发分支 codex/phase-4-ml-walk-forward，起点65f1bca；本轮仅完成验收文档收尾及其Git/CI核实，保留该分支。
- 保留已有历史、稳定 main、phase-2-data-universe 和 Phase 3 分支；不 force push，不改变仓库可见性或改其他仓库。
- Phase 4 收尾完成后停止；不进入 Phase 5–6，不创建正式产品 Release。
- 开始先完整阅读 `docs/PROJECT_PLAN.md`、README、本文件及相关已有代码。
- 用户当前请求决定任务范围；计划书描述的未来功能不等于授权现在实现。
- 每轮先检查现有文件、Git 状态、Python 环境；不覆盖用户成果，不重置已有改动。
- 仅创建当前阶段实际使用的文件，保持模块化单体、简单可测试设计。
- 新阶段开始前更新此阶段状态；不因一次测试成功自行跨越阶段。

## 架构与时间正确性

- CLI 是薄入口；配置、错误、数据读取可独立调用。未来 UI 复用服务逻辑。
- 未来 domain/策略/组合/执行核心不得依赖具体行情供应商或 UI。
- 全部历史输入必须满足 `available_at <= decision_at < execution_at`。
  收盘后信号默认下一合法交易日成交；禁止同日收盘生成信号并同价成交。
- 训练按全局交易日期分组，禁止随机打散；预处理只能在训练窗 fit。
- 标签保留 start/end/known_at，边界执行 purge，必要时 embargo；不可知标签不得训练。
- PIT/当前快照/静态样本明确区分；财报、行业、因子按可得时间使用。
- 时间正确性不能确认时阻断或降级描述性研究，禁止声称可信 OOS。
- 后续实现时加入计划书 4.5 的未来扰动、fold 边界、时间可得性及成交反泄漏测试。
  Phase 0 的样例完整性检查不是完整研究系统的反泄漏证明。

## 环境与质量门槛

- Python 3.12，uv 0.13.6；`pyproject.toml` 与 `uv.lock` 一起维护，不手写锁文件。
- 只添加本阶段所需依赖；核查官方兼容信息，解析后用安装元数据和实际运行验证。
- 使用 `uv sync --locked` 安装，日常检查使用 `uv run --locked --offline …`。
- 验收命令以 README 为准：pytest、Ruff lint/format、帮助、配置、样例、构建与安装验证。
- 所有核心新增逻辑有正常、边界和异常路径验证；不删除失败用例掩盖问题。
- 测试和样例不联网、不依赖 API Key 或动态时间，结果必须确定。
- stdout 为机器可读 JSON；诊断日志 stderr；预期用户错误统一退出 2。
- 不谎称未运行的测试通过，不把本机通过写成远端 GitHub Actions 已通过。
- 变更后更新架构决策、CHANGELOG 和阶段验收记录，列出命令、结果与限制。

## 数据与协作

- Long-only、无杠杆、模拟优先；不接真实券商、不自动下单、不擅自创建付费资源。
- 不提交密钥、账户信息、私人持仓或未获授权的数据。原始真实数据默认保留本地。
- 样例显式标注 synthetic、USD、时间假设；允许展示实际计算的合成回测指标，
  必须明确其不是市场证据；禁止硬编码或虚构收益及模型指标。
- 先解释新概念目的，再写简单实现；最终交代已实现、验证命令、风险、差异和下一阶段依赖。
- 完成后等待用户确认；分支保持单阶段范围，提交须清晰，不擅自 push 或发布。
