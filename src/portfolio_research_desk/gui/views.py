"""Approved report language adapted to Streamlit controls, with shared formatters."""

import io
import re
import zipfile
from html import escape

import streamlit as st

from portfolio_research_desk.report_design import RESEARCH_CSS, metric

STYLE = """
<style>
.stApp {color:#182d40;background:#edf2f5;font-family:'Segoe UI',Arial,sans-serif;
font-variant-numeric:tabular-nums;}
.stMainBlockContainer {max-width:1140px;background:white;padding:2.5rem 2.6rem;
border:1px solid #dce4e9;border-radius:14px;margin:1.5rem auto;}
h1 {color:#182d40;letter-spacing:-.8px;} h2,h3 {color:#182d40;}
[data-testid="stSidebar"] {background:#edf2f5;}
.prd-identity {border-bottom:2px solid #087f8c;padding-bottom:16px;margin-bottom:20px;}
.prd-eyebrow {color:#087f8c;letter-spacing:1.8px;font-size:11px;font-weight:700;}
.prd-cards {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:14px 0;}
.metric {border:1px solid #dce4e9;border-radius:8px;padding:15px 16px;min-width:0;}
.metric.primary {background:#182d40;color:white;}
.metric p,.metric small {font-size:12px;margin:0;}
.metric strong {display:block;font-size:25px;overflow-wrap:anywhere;margin:8px 0;}
.stButton button,.stDownloadButton button {border-radius:5px;}
@media(max-width:720px){.stMainBlockContainer{padding:1.3rem 1rem;margin:0;border:0;}
.prd-cards{grid-template-columns:repeat(2,minmax(0,1fr));}.metric{padding:12px;}
.metric strong{font-size:21px;line-height:1.3;}}
</style>
"""
STYLE += "<style>:root {--line:#dce4e9;--muted:#526577;}" + RESEARCH_CSS + "</style>"


def identity(title, scope):
    st.markdown(
        '<div class="prd-identity"><p class="prd-eyebrow">PORTFOLIO RESEARCH DESK</p>'
        f"<h1>{escape(title)}</h1><p>{escape(scope)}</p></div>",
        unsafe_allow_html=True,
    )


def cards(values):
    st.markdown(
        '<div class="prd-cards">'
        + "".join(
            metric(label, value, note, f"gui-card-{i}", i == 0)
            for i, (label, value, note) in enumerate(values)
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def chart(svg):
    st.markdown(svg, unsafe_allow_html=True)


def report_download(service, ref):
    ref = service.task(ref.command_id)
    directory = service.path(ref.directory)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in directory.rglob("*"):
            if path.is_file():
                service.path(service.relative(path))
                bundle.write(path, path.relative_to(directory).as_posix())
    st.download_button(
        "下载完整报告与审计文件 ZIP",
        output.getvalue(),
        file_name=f"prd-{ref.command_id[:8]}.zip",
        mime="application/zip",
    )
    st.caption("解压后打开 report.html（示例为 index.html）。打印：A4、纵向、100%、背景图形开启。")
    html = directory / ("index.html" if ref.kind == "demo" else "report.html")
    if html.is_file():
        with st.expander("查看已批准的 HTML 报告版式（只读预览）"):
            st.caption("审计文件和可点击的完整报告链接位于上方 ZIP；此处仅预览版式。")
            # Relative file links aren't app routes. Keep them as text in this preview.
            preview = re.sub(r"<a\b[^>]*>", "<span>", html.read_text("utf-8"))
            preview = preview.replace("</a>", "</span>")
            st.iframe(preview, height=850)
