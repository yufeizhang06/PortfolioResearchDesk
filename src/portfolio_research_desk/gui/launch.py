"""Fixed local-only launcher, also usable from an installed wheel."""

import importlib.util
import sys
from pathlib import Path


def main():
    if importlib.util.find_spec("streamlit") is None:
        print("GUI 组件尚未安装。请先双击 Setup GUI.cmd 完成一次性安装。", file=sys.stderr)
        return 2
    from streamlit.web.cli import main as streamlit_main

    sys.argv = [
        "streamlit",
        "run",
        str(Path(__file__).with_name("app.py")),
        "--server.address=127.0.0.1",
        "--server.port=8501",
        "--browser.gatherUsageStats=false",
        "--server.headless=false",
        "--server.fileWatcherType=none",
        "--theme.base=light",
        "--theme.primaryColor=#087f8c",
        "--theme.backgroundColor=#ffffff",
        "--theme.secondaryBackgroundColor=#edf2f5",
        "--theme.textColor=#182d40",
        "--theme.font=sans serif",
    ]
    return streamlit_main()


if __name__ == "__main__":
    raise SystemExit(main())
