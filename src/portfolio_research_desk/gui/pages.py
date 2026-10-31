"""Thin pages for the first research journey and saved-result browsing."""

import csv
import io
import re
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st

from portfolio_research_desk.app_contracts import FactorRequest, HistoryRequest
from portfolio_research_desk.app_services import preview_watchlist
from portfolio_research_desk.data_contracts import validate_quality
from portfolio_research_desk.domain import fingerprint, jsonable
from portfolio_research_desk.errors import DataError, ProjectError
from portfolio_research_desk.gui.views import cards, chart, identity, report_download
from portfolio_research_desk.report_design import line_chart, money, number, percent, pvalue, stamp

STATUS = {"complete": "已完成", "partial": "部分结果", "failed": "失败"}


def attempt(operation):
    try:
        return operation()
    except (ProjectError, OSError, ValueError) as exc:
        st.error(str(exc))
        st.warning("本次操作未完成。下方已保存结果为历史结果，可继续查看或新建任务重试。")
        return None


def command(kind):
    key = "desk_command_" + kind
    if key not in st.session_state:
        st.session_state[key] = uuid4().hex
    return st.session_state[key]


def new_command(kind):
    if st.button("新实验 / 重试", key="desk_new_" + kind):
        st.session_state["desk_command_" + kind] = uuid4().hex
        st.session_state.pop("desk_check_" + kind, None)
        st.success("已准备新任务；提交后才会运行。")


def task_options(service, kind):
    return [ref for ref, _ in service.tasks() if ref and ref.kind == kind]


def task_label(ref):
    return (
        f"{stamp(ref.generated_at)} · {ref.data_kind} · "
        f"{STATUS.get(ref.status, ref.status)} · {ref.command_id[:8]}"
    )


def recent_tasks(service):
    tasks = service.tasks()
    if not tasks:
        st.info("尚无数据。到 Stock Explorer 保存自选股并获取行情，再进入 Research。")
    for ref, error in tasks:
        if error:
            st.warning("未完成 / 完整性失败：" + error)
        else:
            st.write(f"**{ref.kind}** · {task_label(ref)}")
    return tasks


def account_selector(service):
    accounts = []
    for path in sorted(service.root.rglob("*.sqlite3")):
        relative = service.relative(path)
        service.path(relative)
        accounts.append(relative)
    preferred = st.session_state.get("desk_selected_account")
    options = [None, *accounts]

    def label(value):
        if not value:
            return "尚未选择账户"
        parts = Path(value).parts
        if parts[:2] == ("gui", "tasks"):
            return f"合成示例账户 · {parts[2][:8]}"
        return f"本地账户 · {Path(value).stem} · {Path(value).parent.name}"

    selected = st.selectbox(
        "当前 Paper 账户（工作区内）",
        options,
        index=options.index(preferred) if preferred in options else 0,
        format_func=label,
        key="desk_account",
    )
    st.session_state.desk_selected_account = selected
    if selected:
        with st.expander("账户文件位置（审计）"):
            st.caption(selected)
    return selected


def account_overview(service, selected):
    summary = service.read_account(selected) if selected else None
    valuation = summary["last_recorded_valuation"] if summary else None
    stale = summary["valuation_stale"] if summary else False
    pending = sum(p["status"] == "PENDING_REVIEW" for p in summary["plans"]) if summary else 0
    cards(
        [
            (
                "最近记录 NAV",
                money(valuation.nav_cad) if valuation else "尚未估值",
                "CAD · 历史快照",
            ),
            (
                "现金市值",
                money(valuation.cash_cad) if valuation else "尚未估值",
                "按记录汇率折合 CAD",
            ),
            (
                "持仓市值",
                money(sum((p["value_cad"] for p in valuation.positions), Decimal(0)))
                if valuation
                else "尚未估值",
                "按记录价格折合 CAD",
            ),
            ("待审核计划", str(pending) if summary else "尚无账户", "人工审核 · 纯模拟"),
        ]
    )
    if summary:
        if stale:
            st.warning(
                "需要重新估值：账本经济状态已变化，或尚无估值。以上为历史记录。首版不提供写入。"
            )
        if valuation:
            st.caption(f"估值时间：{stamp(valuation.as_of)} · 历史报价不代表当前行情")
        st.caption(
            f"账本最后事件：{stamp(summary['last_event_at'])} · {summary['event_count']} 个事件"
        )
    return summary


def home(service):
    identity("Home Dashboard", "本地工作区 · CAD Paper 历史估值 · 研究与模拟结果分开呈现")
    selected = account_selector(service)
    account_overview(service, selected)
    st.subheader("开始研究")
    st.write(
        "① Stock Explorer：确认证券身份并保存行情 → "
        "② Research：检查输入、运行 FF3/FF4 → ③ 导出报告。"
    )
    left, right = st.columns(2)
    left.page_link(st.session_state.desk_pages["explorer"], label="管理自选股与行情")
    right.page_link(st.session_state.desk_pages["research"], label="运行因子研究")
    with st.expander("运行合成示例 · 独立 3,000 CAD 账户"):
        st.write("将调用已验收的离线示例，创建新目录和新账户。独立 USD 回测不与 CAD 收益合并。")
        st.caption("该固定示例内部包含仅限 synthetic 的脚本审核，不是用户账户的审核入口。")
        new_command("demo")
        if st.button("运行独立合成示例", key="desk_demo"):
            with st.spinner("正在运行现有离线工作流…"):
                ref = service.demo(command("demo"))
            st.success("合成示例已完成；已有账户未被写入。")
            report_download(service, ref)
    st.subheader("最近任务")
    recent_tasks(service)
    with st.expander("环境诊断（只读）"):
        env = service.inspect()
        st.write(f"Python {env['python_version']} · SQLite {env['sqlite_version']}")
        st.dataframe(
            [
                {"模块": k, "状态": "可用" if v["available"] else "未安装"}
                for k, v in env["extras"].items()
            ],
            hide_index=True,
        )


def explorer(service):
    identity("Stock Explorer & Watchlists", "US / USD · 用户静态自选池 · 不具备历史 PIT 成分认证")
    st.subheader("1. 确认并保存自选股")
    synthetic = (
        st.radio("列表数据身份", ["synthetic 合成样例", "real 真实证券"], key="desk_list_kind")
        == "synthetic 合成样例"
    )
    symbols = st.text_area(
        "股票代码（逗号或换行分隔）",
        value="SYN_FACTOR" if synthetic else "",
        key="desk_symbols_" + str(synthetic),
    )
    st.caption("内置因子样例使用 SYN_FACTOR。真实证券需确认完整身份；名称不会由系统猜测。")
    upload = st.file_uploader("或导入自选股 CSV", type=["csv"], key="desk_watchlist_upload")
    if upload:
        text = upload.getvalue().decode("utf-8-sig")
        assets, duplicates, errors = preview_watchlist(text, synthetic)
        if errors:
            st.error("；".join(errors))
        if duplicates:
            st.warning(f"重复项所在行：{duplicates}；保存时去重。")
        rows = jsonable(assets)
    else:
        rows = [
            {"market": "US", "exchange": "XNAS", "symbol": symbol, "currency": "USD"}
            for symbol in re.split(r"[\s,]+", symbols.strip().upper())
            if symbol
        ]
    with st.form("desk_watchlist_form"):
        edited = st.data_editor(
            pd.DataFrame(rows, columns=["market", "exchange", "symbol", "currency"]),
            num_rows="dynamic",
            hide_index=True,
            key="desk_identity_" + fingerprint([rows, synthetic])[:12],
        )
        st.caption(
            "请逐行确认 market / exchange（MIC）/ symbol / currency；默认 XNAS 不代表身份已核实。"
        )
        name = st.text_input("自选列表名称", "my-watchlist", key="desk_list_name")
        confirmed = st.checkbox("我已逐行确认证券身份和数据种类", key="desk_identity_confirm")
        saved = st.form_submit_button("保存自选列表")
    if saved:
        if not confirmed:
            raise DataError("请先确认每行证券身份。")
        text = edited.to_csv(index=False)
        assets, duplicates, errors = preview_watchlist(text, synthetic)
        if errors:
            raise DataError("；".join(errors))
        if duplicates:
            st.warning(f"重复行 {duplicates} 已去重。")
        old_assets = set()
        for path in service.lists():
            if path.rsplit("/", 1)[-1].startswith(name + "-"):
                old_assets.update(service.load_list(path).assets)
        st.caption(
            f"与同名保存版本比较：新增 {len(set(assets) - old_assets)}；"
            f"移除 {len(old_assets - set(assets))}。"
        )
        service.save_list(name, assets, synthetic)
        st.success("自选列表已保存为独立版本，可重启后重新打开。")
    lists = service.lists()
    if not lists:
        st.info("保存列表后可获取行情。")
        return
    selected = st.selectbox(
        "已保存自选列表",
        lists,
        key="desk_selected_list",
        format_func=lambda p: Path(p).stem.rsplit("-", 1)[0] + " · " + Path(p).stem[-16:-8],
    )
    snapshot = service.load_list(selected)
    st.dataframe(jsonable(snapshot.assets), hide_index=True)
    st.caption(
        f"{'synthetic' if snapshot.synthetic else 'real'} · user_static · "
        f"列表保存时间 {stamp(snapshot.as_of)}"
    )
    stream = io.StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["market", "exchange", "symbol", "currency"])
    writer.writerows((a.market, a.exchange, a.symbol, a.currency) for a in snapshot.assets)
    st.download_button("导出自选股 CSV", stream.getvalue(), "watchlist.csv", "text/csv")
    st.subheader("2. 获取并检查行情")
    new_command("history")
    with st.form("desk_history_form"):
        source = st.selectbox(
            "行情来源",
            ["synthetic", "local", "yfinance"],
            help="synthetic 仅为 SYN_FACTOR；local 使用工作区内原生文件；yfinance 需明确允许联网。",
        )
        left, right = st.columns(2)
        start = left.date_input("行情开始日期", date(2024, 1, 1))
        end = right.date_input("行情结束日期（不含）", date(2024, 6, 1))
        local = st.text_input(
            "本地行情相对路径（仅 local）", help="原生 CSV + .metadata.json，或原生 Parquet。"
        )
        network = st.checkbox("允许本次向 yfinance 获取网络数据", value=False)
        refresh = st.checkbox("强制刷新（新快照）", value=False)
        stale = st.checkbox("明确允许使用过期缓存（会标明过期）", value=False)
        submitted = st.form_submit_button("获取行情")
    if submitted:
        request = HistoryRequest(
            snapshot.assets,
            start,
            end,
            source,
            local or None,
            "synthetic" if snapshot.synthetic else "real",
            network,
            refresh,
            stale,
        )
        with st.spinner("正在通过既有数据服务读取并校验…"):
            ref = attempt(lambda: service.fetch(request, command("history")))
        if ref:
            st.success(f"行情任务：{STATUS[ref.status]}。")
    histories = task_options(service, "history")
    if histories:
        ref = st.selectbox(
            "已保存行情任务", histories, format_func=task_label, key="desk_history_task"
        )
        document = service.history_result(ref)
        for failure in document["failures"]:
            st.error(f"{failure['asset']['symbol']}：{failure['reason']}")
        for event in document["cache_events"]:
            if event.get("stale"):
                st.warning("当前结果使用过期缓存；日期和来源保留在快照中。")
        options = service.histories(ref)
        if options:
            selected_history = st.selectbox(
                "价格快照", options, format_func=lambda x: f"{x[0].symbol} / {x[0].exchange}"
            )
            history = service.history(selected_history[1])
            quality = validate_quality(history)
            cards(
                [
                    ("接受观察", str(len(quality.accepted)), history.data_kind + " · USD"),
                    ("隔离观察", str(len(quality.quarantined)), "不填造缺失价格"),
                    ("质量问题", str(len(quality.issues)), "完整原因见下表"),
                    (
                        "数据范围",
                        str(min(r.session_date for r in history.rows)),
                        "至 " + str(max(r.session_date for r in history.rows)),
                    ),
                ]
            )
            st.caption(f"来源：{history.provider} · 价格口径：{history.price_basis}")
            st.caption(
                f"获取时间 {stamp(history.retrieved_at)} · 可得性口径 {history.availability_basis}"
            )
            chart(
                line_chart(
                    [str(r.session_date) for r in quality.accepted],
                    [("Close / USD", [r.close for r in quality.accepted])],
                    "gui-prices",
                    "价格曲线 · USD",
                    number,
                )
            )
            with st.expander("质量、时间与来源明细"):
                st.dataframe(jsonable(quality.issues), hide_index=True)
                st.dataframe(
                    [
                        {
                            "日期": r.session_date,
                            "观察结束 UTC": stamp(r.observation_end),
                            "可得 UTC": stamp(r.available_at),
                        }
                        for r in history.rows
                    ],
                    hide_index=True,
                )
                for note in history.limitations:
                    st.write(note)
            if st.button("加入因子研究"):
                st.session_state.desk_history_reference = selected_history[1]
                st.switch_page(st.session_state.desk_pages["research"])
    st.info("真实池自动历史回测尚未支持；当前快照和自选静态池不能宣称历史 PIT 成分。")


def research(service):
    identity(
        "Research & Factor Analysis", "事后描述性归因 · USD · Alpha 按观察期呈现 · 不生成交易信号"
    )
    if not service.capabilities()["factors"]:
        st.warning("缺少 factors 组件。关闭应用后运行 Setup GUI.cmd，再重新打开。")
        return
    options = [
        (asset, path)
        for ref in task_options(service, "history")
        for asset, path in service.histories(ref)
    ]
    if not options:
        st.info("尚无行情。请到 Stock Explorer 保存自选股并获取行情。")
        return
    preferred = st.session_state.get("desk_history_reference")
    index = next((i for i, (_, path) in enumerate(options) if path == preferred), 0)
    selected = st.selectbox(
        "研究价格快照",
        options,
        index=index,
        format_func=lambda x: f"{x[0].symbol} / {x[0].exchange} · {x[1].split('/')[2][:8]}",
    )
    history = service.history(selected[1])
    st.caption(f"{history.data_kind} · {history.provider} · 快照 {history.snapshot_hash[:16]}")
    new_command("factor")
    with st.form("desk_factor_form"):
        left, right = st.columns(2)
        start = left.date_input("研究开始日期", min(r.session_date for r in history.rows))
        end = right.date_input(
            "研究结束日期（不含）", max(r.session_date for r in history.rows) + timedelta(days=1)
        )
        source = st.selectbox(
            "因子来源", ["synthetic", "local"], index=0 if history.data_kind == "synthetic" else 1
        )
        frequency = st.selectbox("观察频率", ["daily", "monthly"])
        st.caption("固定共同样本同时比较 FF3 / Carhart FF4；合成因子仅支持日频。")
        covariance = st.selectbox("协方差", ["HC3", "nonrobust"])
        basis = st.selectbox("收益价格基础", ["adjusted_close", "close"])
        confidence = st.number_input("置信水平", min_value=0.50, max_value=0.999, value=0.95)
        min_obs = st.number_input("最少共同观察数", min_value=6, value=20, step=1)
        window = st.number_input("滚动窗口（观察期数）", min_value=6, value=32, step=1)
        with st.expander("本地因子与月频输入（仅 local）"):
            ff3 = st.text_input("FF3 文件相对路径")
            momentum = st.text_input("Momentum 文件相对路径")
            sessions = st.text_input("交易会话日期文件相对路径（月频必填）")
            st.caption(
                "使用已有 French 格式文件；会话文件每行一个 ISO 日期，包含前一月。"
                "无需编辑 TOML/JSON。"
            )
        checked = st.form_submit_button("检查输入")
        submitted = st.form_submit_button("运行因子研究")
    request = FactorRequest(
        selected[1],
        start,
        end,
        frequency,
        source,
        ff3 or None,
        momentum or None,
        sessions or None,
        covariance,
        confidence,
        int(min_obs),
        int(window),
        basis,
    )
    check_key = fingerprint(repr(request))
    if checked:
        with st.spinner("正在使用既有后端检查共同样本与回归可行性（不保存）…"):
            result = attempt(lambda: service.check_factor(request))
        st.session_state.pop("desk_check_factor", None)
        if result:
            st.session_state.desk_check_factor = check_key
            st.session_state.desk_check_summary = {
                "nobs": len(result.sample.rows),
                "status": result.status,
                "warnings": list(result.warnings),
            }
    if st.session_state.get("desk_check_factor") == check_key:
        summary = st.session_state.desk_check_summary
        st.info(
            f"检查完成：共同样本 {summary['nobs']}；后端状态 {STATUS[summary['status']]}。"
            "运行后保存完整诊断。"
        )
        for warning in summary["warnings"]:
            st.caption(warning)
    if submitted:
        if st.session_state.get("desk_check_factor") != check_key:
            st.error("输入已变化或尚未检查。请先点击“检查输入”。")
            st.caption("下方为已保存的历史结果。")
        else:
            with st.spinner("正在拟合 FF3/FF4、计算既有诊断并保存不可变报告…"):
                ref = attempt(lambda: service.study(request, command("factor")))
            if ref:
                st.success(f"研究任务：{STATUS[ref.status]}；结果已保存。")
    refs = task_options(service, "factor")
    if refs:
        st.subheader("已保存结果")
        ref = st.selectbox("因子研究任务", refs, format_func=task_label)
        show_factor(service, ref)


def show_factor(service, ref):
    data = service.factor_data(ref)
    run = data["run"]
    fits = data["analysis"]["fits"] if data["analysis"] else {}
    ff4 = fits.get("FF4", {})
    coefficients = ff4.get("coefficients", {})
    period = "日" if run["config"]["frequency"] == "daily" else "月"
    st.caption(
        f"{run['data_kind']} · USD · 生成 {stamp(run['generated_at'])} · "
        f"状态 {STATUS[run['status']]}"
    )
    st.caption(
        f"样本请求：{run['config']['start']} 至 {run['config']['end']}（不含）；"
        "未认证真实 PIT/OOS。"
    )
    st.warning("事后描述性研究：显著 Alpha 不代表可交易超额收益，不能据此直接下单。")
    if not fits:
        st.error("回归失败：没有可用系数；请查看警告与样本诊断。")
    cards(
        [
            (
                "FF4 Alpha",
                percent(coefficients.get("Alpha", {}).get("estimate"), 4),
                f"每{period} · 超额收益截距",
            ),
            (
                "Market Beta",
                number(coefficients.get("Mkt-RF", {}).get("estimate"), 3),
                "市场超额收益暴露",
            ),
            ("R²", percent(ff4.get("r_squared")), "样本内解释比例"),
            ("共同观察数", str(run["nobs"]), "FF3 / FF4 使用相同行"),
        ]
    )
    overview, details, methodology = st.tabs(
        ["Overview 概览", "Details 明细", "Methodology 方法与下载"]
    )
    with overview:
        st.write("Alpha 是扣除因子解释后的拟合截距；Beta 表示敏感度；R² 衡量样本拟合程度。")
        st.dataframe(
            [
                {
                    "模型": model,
                    "R²": percent(fit["r_squared"]),
                    "调整 R²": percent(fit["adjusted_r_squared"]),
                    "AIC": number(fit["aic"]),
                    "BIC": number(fit["bic"]),
                    "观察数": fit["nobs"],
                }
                for model, fit in fits.items()
            ],
            hide_index=True,
        )
        rolling = data["rolling"]
        chart(
            line_chart(
                [row["window_end"] for row in rolling],
                [
                    (
                        term,
                        [
                            row["comparison"]["fits"]["FF4"]["coefficients"][term]["estimate"]
                            if row["status"] == "complete"
                            else None
                            for row in rolling
                        ],
                    )
                    for term in ("Mkt-RF", "SMB", "HML", "Mom")
                ],
                "gui-rolling",
                "滚动 FF4 暴露 · 无量纲 Beta",
                lambda v: number(v, 2),
            )
        )
        st.caption("失败窗口显示为断点；不填造系数。")
    with details:
        rows = []
        for model, fit in fits.items():
            for term, coefficient in fit["coefficients"].items():
                fmt = (lambda v: percent(v, 4)) if term == "Alpha" else (lambda v: number(v, 3))
                rows.append(
                    {
                        "模型": model,
                        "系数": term,
                        "单位": f"% / {period}" if term == "Alpha" else "无量纲",
                        "估计": fmt(coefficient["estimate"]),
                        "标准误": fmt(coefficient["std_error"]),
                        "t": number(coefficient["t_statistic"], 2),
                        "p": pvalue(coefficient["p_value"]),
                        "置信区间": (
                            f"{fmt(coefficient['ci_lower'])} 至 {fmt(coefficient['ci_upper'])}"
                        ),
                    }
                )
        st.dataframe(rows, hide_index=True)
        st.caption(f"Alpha、标准误与区间为百分比每{period}；原始导出保留全部精度。")
        st.dataframe(
            [
                {
                    "窗口开始": r["window_start"],
                    "窗口结束": r["window_end"],
                    "观察数": r["nobs"],
                    "状态": STATUS[r["status"]],
                    "原因": r.get("reason", ""),
                }
                for r in data["rolling"]
            ],
            hide_index=True,
        )
        for model, fit in fits.items():
            st.write(f"{model} 诊断")
            st.dataframe(
                [
                    {"诊断": key, "结果": str(value)}
                    for key, value in fit.get("diagnostics", {}).items()
                ],
                hide_index=True,
            )
    with methodology:
        for warning in run["warnings"]:
            st.write(warning)
        st.write(f"价格来源：{data['price_snapshot']['provider']}")
        st.caption(
            f"价格获取：{stamp(data['price_snapshot']['retrieved_at'])}；获取时钟不证明历史发布时间。"
        )
        report_download(service, ref)


def models(service):
    identity("ML & Backtesting", "首个 GUI 版本的实现范围")
    st.info(
        "本轮优先交付 Home → Stock Explorer → Research。模型实验和 USD 回测表单待后续独立验收。"
    )
    st.warning("真实股票池自动历史回测、可信真实 OOS 与真实 ML 部署尚未支持。")


def paper(service):
    identity("Portfolio & Paper Trading", "CAD · 纯模拟 · 只读账户查询")
    selected = account_selector(service)
    summary = account_overview(service, selected)
    if summary:
        st.subheader("现金余额（原币种）")
        st.dataframe(
            [
                {"币种": currency, "余额": money(amount, currency)}
                for currency, amount in summary["cash"]
            ],
            hide_index=True,
        )
        st.subheader("计划状态")
        st.dataframe(jsonable(summary["plans"]), hide_index=True)
    st.info("首版不提供提案、审核、成交或估值写入；现有账本风险控制和人工审核保持在后端。")


def reports(service):
    identity("Reports & Settings", "已保存结果 · 每次打开检查完整性 · 原始导出位于下载入口")
    tasks = recent_tasks(service)
    refs = [ref for ref, _ in tasks if ref and ref.kind in {"factor", "demo"}]
    if refs:
        ref = st.selectbox("打开结果", refs, format_func=lambda r: r.kind + " · " + task_label(r))
        if ref.kind == "factor":
            show_factor(service, ref)
        else:
            report_download(service, ref)
    st.caption("工作区切换在左侧完成。所有显示时钟为 UTC，输入日期为数据会话日期。")
