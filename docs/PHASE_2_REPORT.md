# Phase 2 本地验收报告

日期：2026-10-27（America/Toronto）。版本 0.3.0，分支 `phase-2-data-universe`。
**本地结论：Phase 2 功能验收通过，不进入 Phase 3。**

> 后续状态：用户已确认验收，并授权首次 GitHub Private 上传。修复新 checkout 测试目录问题后，
> Ubuntu/Windows 远程 CI 均实际通过（各 208 tests，含构建和独立安装）。
> [运行记录](https://github.com/yufeizhang06/PortfolioResearchDesk/actions/runs/40544579916)
> 与失败/修复过程详见 DEVELOPMENT_LOG。以下本地验收命令及实测结果保留原记录。

## 基线与范围核实

- 起点为首次本地提交 `86dc6824efa0754aa53e4b5263c4352113339d0c`，开始时工作区干净、无远端。
  Phase 0–1 已有 141 个测试；Phase 1 仍是明确的合成数据回测，不能误写为真实行情回测。
- 已读取 AGENTS、完整原始计划、README、开发日志及实现/验收记录；没有阶段阻塞。
- 计划书 Phase 2 规定 yfinance / CSV / Parquet、缓存、失败重试、自选列表、至少一个美国市场入口、
  三种筛选规则、Universe 标签和数据质量报告；没有授权进入因子/ML/真实交易。
- README 原先正确描述 Phase 1，但不再代表新实现；本轮按实际实现更新，并新增数据政策。
- 原始计划没有改动；SHA-256 仍为
  `1f208c70b41aeaecfac45f1e38bcd2d3ff674f6eb1868352b45fd9eb40f752bb`。

## 交付与验收映射

| 计划要求 | 实际交付与验证 |
|---|---|
| yfinance Adapter | 真实 US/USD 日线，显式全部价格选项、身份/时区/日期/schema 验证；AAPL/MSFT 实际接口运行 |
| CSV / Parquet | native 元数据契约、CSV sidecar 校验、Parquet 内嵌元数据；合成及真实无损往返 |
| 缓存与失败恢复 | SQLite + 不可变 JSON 快照，TTL/offline/refresh/stale、损坏检测与显式修复；超时/限流/缺失/部分失败测试 |
| Custom Watchlist | CSV 导入导出、JSON 保存读取、增删更新、完整身份去重、不可伪造 PIT |
| Market 入口 | Nasdaq Trader 官方当前上市证券目录，source/as_of/available_at/current_snapshot、排除原因与覆盖警告 |
| Screening | 最少历史 + 成交额近似 + 过去价格动量 + 历史波动率；AND 组合、入选/剔除与可得时点 |
| 三模式及组合 | custom / market / screening、Custom + Screening、Market + Screening、Market + 自选补充；同一工作流 |
| PIT / 反泄漏 | 历史 PIT 要求阻断当前/未验证快照；晚可得拒绝；未来扰动不改变过去筛选；未宣称可信 OOS |
| 数据质量 | 重复/缺失/OHLC/volume/币种/时间/跳变/公司行为检查与隔离；日历未验证明确警告 |
| 复现输出 | config、provenance、数据哈希、缓存事件、质量、筛选、完整观察值与逐资产 CSV；run.json 最后写入 |
| 兼容与工程 | 原 Phase 0/1 测试与 CLI 保留；可安装包、Ruff、锁文件、扩展离线 CI 与独立安装验证 |

## 环境与依赖

Python **3.12.14** / uv **0.13.6**；项目仍限定 Python 3.12 系列。
只在可选 `data` extra 增加 yfinance、PyArrow，由 uv 实际解析并维护 uv.lock（38 个锁定包）。
基础安装和 native CSV / 合成研究无需第三方运行库。

| 实际安装版本 | 安装元数据 Requires-Python | 验证 |
|---|---|---|
| yfinance 1.7.0 | 未声明 | 不推定版本兼容；已在 Python 3.12 实际导入和请求 |
| PyArrow 26.0.0 | >=3.11 | Parquet 真实/合成往返成功 |
| pandas 3.1.0 | >=3.11 | yfinance 依赖；真实响应与确定性注入测试 |
| NumPy 2.5.4 | >=3.12 | 依赖安装、导入及实际工作流成功 |

开发工具沿用锁定版本 pytest 9.1.1、pytest-socket 0.8.1、Ruff 0.17.3、Hatchling 1.32.4。
版本范围负责声明支持面，精确解析与下载哈希由 uv.lock 固定；没有手写锁文件。

## 真正执行的本地检查

下列 `uv` 可替换为本机 `work/bin/uv.exe`，不需要修改全局 PATH。
本轮 uv 缓存设置在 `work/uv-cache-phase1`。缓存/报告目录均被 Git 忽略。

```powershell
uv lock --check --offline
uv sync --locked --extra data --offline
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
uv run --locked --offline pytest -p pytest_socket -q --tb=short --basetemp=work/phase2-final-tests -o cache_dir=work/phase2-final-cache
uv run --locked --offline ruff check .
uv run --locked --offline ruff format --check .
uv run --locked --offline prd --help
uv run --locked --offline prd --version
uv run --locked --offline prd config validate --config configs/example_offline.toml
uv run --locked --offline prd demo
uv run --locked --offline prd config validate --kind backtest --config configs/example_backtest.toml
uv run --locked --offline prd backtest run --config configs/example_handcheck.toml
uv run --locked --offline prd config validate --kind research --config configs/example_research_offline.toml
uv run --locked --offline prd universe build
uv run --locked --offline prd data fetch --config configs/example_research_offline.toml
uv build --no-cache --offline --no-build-isolation --out-dir dist/phase2
uv run --locked --offline python scripts/verify_distribution.py dist/phase2 --uv <本机 uv 可执行文件>
```

- 全量测试：**208 passed**，包括原有 141 个测试；最终独立临时目录运行无警告。
  确定性测试禁止 socket，不需要密钥或外部行情；注入响应只验证本地逻辑，独立于下面的真实请求。
- Ruff lint 与 format 通过；uv lock 一致性检查和锁定安装成功。
- 新旧帮助、配置、demo、合成回测及 Phase 2 默认流程均执行；可独立 venv 安装而非只在源码目录运行。
- wheel / sdist 构建成功；sdist 离线重建 wheel，直接 wheel 和重建 wheel 分别安装到干净 venv，
  切换源码目录以外运行 Phase 0/1/2 CLI 及包内资源，均通过；此基础安装不安装 data extra。
- 最终代码测试新增导出往返、导出失败无完成标记、HTTP-date Retry-After、缺失供应商元数据等边界。
- 早期运行遇到旧 pytest 缓存写权限警告；换本轮目录后消除。构建曾因 Windows 临时目录权限失败，
  经批准以普通本机权限重新执行，成功。没有把失败尝试当成通过。

## 真实接口与缓存集成验收

2026-10-27 实际运行（这里不是 fixture 或 Mock）：

```powershell
uv run --locked --offline prd data fetch --config configs/example_real_research.toml
uv run --locked --offline prd universe build --config configs/example_market_research.toml
uv run --locked --offline prd universe build --config configs/example_market_research.toml --offline
```

| 实测流程 | 结果 |
|---|---|
| Yahoo 直接探测 AAPL | 2026-10-01 至 exclusive 2026-10-27，18 行，接受 18 / 隔离 0；未知日历/历史 PIT 等仍警告 |
| Nasdaq 官方目录探测 | 4,328 个保留证券，1,297 个按 ETF/Test/NextShares 排除；仅当前快照，不代表普通股全集或历史成员 |
| Custom + Screening | AAPL/MSFT 各 18 行，real、user_static、complete；首次两资产缓存 0/2 |
| Market + Screening | 明确 include AAPL/MSFT，real、current_snapshot、complete；缓存 2/3 |
| Market 离线回放 | 同一范围 complete，目录 + 两资产缓存 **3/3 命中**，没有网络回退 |
| 真实 CSV → Parquet → read | 18 行精确相等，包括 Decimal、UTC、来源、可得时间和限制；CLI check 成功 |

直接探测的原始目录 SHA-256：
`df8dee7608a3ae56b28bb9ab629442fdb6c2e8a3ca7c7c2005f3994c738aecb0`；
目录 creation marker 为 `File Creation Time: 1026202621:31|||||||`（保留原文，未擅自推定时区）。
直接 AAPL 标准化 History SHA-256：
`1ff144f84eea48dd2c14f7aea0a31ccfa43e7e0a5967cd54f2895ef264b35a1f`。
多次真实请求 retrieved_at 不同，History 哈希不同是预期行为；缓存回放则保留原快照与哈希。

本地证据位于 `work/phase2-live-probe-result.json`、`work/phase2-real-integration-result.json`、
`work/phase2-final-data-result.json`；原始及标准化真实数据只在忽略目录。
完整新导出报告位于 `outputs/research/20261027T161621-7d8fc85f1e42/`。
目录名使用 UTC，本文日期使用用户本地时区；不会将 UTC 时间解释为本地交易事件。
这些文件不进入 Git 或发行包；文档保留探测摘要与校验指纹便于复查。

## 限制、差异与后续依赖

1. 行情是 Yahoo 经第三方 yfinance，不是交易所官方行情 API；Nasdaq 只有目录来自官方。
   外部服务可能失效或限流，本轮成功不代表 SLA。yfinance 在 pandas 3.1 上出现上游 Pandas4Warning
   （sort_index 的 inplace 参数将来弃用），本轮请求成功；未隐藏警告或随意重排依赖。
2. 未核实历史指数、退市、合并、更名映射、完整市场批量覆盖；没有解决幸存者偏差。
   当前目录按 current_snapshot 保存，require_point_in_time=true 会阻断，不能冒充历史动态成分。
3. 日线真实 event_time 未知；保守日期上界与实际 retrieved_at 明确记录。
   没有权威交易日历和历史发布时间，不能声称可信 OOS，也不把今天下载的数据回填为过去已知。
4. OHLC/Adj Close 分开，未实现公司行为账本、历史成交假设或 FX；真实输入不进入 Phase 1 回测。
   这保留旧接口保证而非缺失静默降级；当前仅描述性股票池研究。
5. Parquet/CSV 支持本项目 native schema；任意外部 CSV 无可靠元数据时不推断。
   目录含非普通股，行业/市值缺少可得时间，因此未添加此类筛选。
6. 本地验收时远程 CI 未验证；后续 GitHub 托管 Ubuntu/Windows 已真实通过，macOS 仍未实机验证。
7. 用户后来授权并完成 Phase 2 Commit 和 Private 上传，保留原始历史；没有真实交易，阶段只到 Phase 2。

后续建议为计划书 Phase 3：French 因子输入、单位与频率检查、FF3/FF4 诊断、OLS/rolling beta
及构造已知答案测试；需用户确认后才开始。当前真实数据不满足历史特征可得性时继续限制为诊断研究。
建议本阶段本地提交消息：`feat: add market data adapters, cache and universe screening`。
