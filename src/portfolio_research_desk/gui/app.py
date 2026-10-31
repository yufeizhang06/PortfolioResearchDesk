"""Local application shell. All business use cases go through DeskService."""

import os
from pathlib import Path

import streamlit as st

from portfolio_research_desk.app_services import DeskService
from portfolio_research_desk.errors import ProjectError
from portfolio_research_desk.gui import pages
from portfolio_research_desk.gui.views import STYLE

st.set_page_config(page_title="PortfolioResearchDesk", layout="wide")
st.markdown(STYLE, unsafe_allow_html=True)
with st.sidebar:
    st.markdown("### PortfolioResearchDesk")
    st.caption("本地研究 · 模拟优先")
    with st.form("workspace"):
        root = st.text_input(
            "工作区位置", value=os.environ.get("PRD_GUI_WORKSPACE", "work/gui-desk")
        )
        opened = st.form_submit_button("打开工作区")
        created = st.form_submit_button("创建工作区")
    if opened or created:
        try:
            desk = DeskService(Path(root))
            if created:
                desk.create()
            desk.inspect()
            # A workspace change clears all page drafts, references and command IDs.
            for name in list(st.session_state):
                if name.startswith("desk_"):
                    del st.session_state[name]
            st.session_state.desk_root = str(desk.root)
        except (ProjectError, OSError, ValueError) as exc:
            st.error(str(exc))
    selected_root = st.session_state.get("desk_root")
    if selected_root:
        st.caption(f"当前工作区：{selected_root}")
        st.caption("数据身份随快照显示 · Paper 只读 · 无券商")
    else:
        st.info("先创建一个新工作区，或打开已有 PRD 工作区。")


def render(function):
    def page():
        if not selected_root:
            st.title("欢迎使用 PortfolioResearchDesk")
            st.write("在左侧创建工作区，然后进入 Stock Explorer → Research。无需编辑配置文件。")
            st.info("内置样例 SYN_FACTOR 为 synthetic / USD，仅验证软件流程。")
            return
        try:
            service = DeskService(Path(selected_root))
            service.inspect()
            function(service)
        except (ProjectError, OSError, ValueError) as exc:
            st.error(str(exc))
            st.info("上次已保存结果仍保留。请修正输入，或点击“新实验 / 重试”。")

    return page


page_definitions = [
    st.Page(render(pages.home), title="Home Dashboard", default=True, url_path="home"),
    st.Page(render(pages.explorer), title="Stock Explorer", url_path="explorer"),
    st.Page(render(pages.research), title="Research", url_path="research"),
    st.Page(render(pages.models), title="ML & Backtesting", url_path="models"),
    st.Page(render(pages.paper), title="Portfolio & Paper", url_path="paper"),
    st.Page(render(pages.reports), title="Reports & Settings", url_path="reports"),
]
navigation = st.navigation(page_definitions)
st.session_state.desk_pages = {"explorer": page_definitions[1], "research": page_definitions[2]}
navigation.run()
