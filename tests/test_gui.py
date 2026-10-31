"""Streamlit form tests; only loopback sockets for the framework's event loop."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from portfolio_research_desk.app_services import DeskService

pytestmark = pytest.mark.allow_hosts(["127.0.0.1", "::1"])
APP = Path(__file__).resolve().parents[1] / "src/portfolio_research_desk/gui/app.py"


def button(app, label):
    return next(b for b in app.button if b.label == label)


def page(root, name):
    return AppTest.from_string(
        "from pathlib import Path\n"
        "from portfolio_research_desk.app_services import DeskService\n"
        f"from portfolio_research_desk.gui.pages import {name}\n"
        f"{name}(DeskService(Path({str(root)!r})))\n",
        default_timeout=30,
    ).run()


def test_first_use_workspace_and_home(tmp_path, monkeypatch):
    root = tmp_path / "first"
    monkeypatch.setenv("PRD_GUI_WORKSPACE", str(root))
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert "欢迎使用" in app.title[0].value
    button(app, "创建工作区").click().run()
    assert not app.exception
    assert (root / "workflow.toml").is_file()
    assert any("尚无数据" in v.value for v in app.info)
    button(app, "创建工作区").click().run()
    assert app.error and not app.exception


def test_explorer_to_research_without_config_editing(tmp_path):
    service = DeskService(tmp_path / "desk")
    service.create()
    app = page(service.root, "explorer")
    button(app, "保存自选列表").click().run()
    assert app.exception  # Thin-page harness has no app shell's expected-error boundary.
    app = page(service.root, "explorer")
    app.checkbox(key="desk_identity_confirm").check()
    button(app, "保存自选列表").click().run()
    assert not app.exception
    button(app, "获取行情").click().run()
    assert not app.exception and service.tasks()[0][0].status == "complete"
    button(app, "获取行情").click().run()
    assert not app.exception and len(service.tasks()) == 1
    research = page(service.root, "research")
    button(research, "检查输入").click().run()
    assert not research.exception
    assert any("共同样本 96" in v.value for v in research.info)
    button(research, "运行因子研究").click().run()
    assert not research.exception
    assert len([ref for ref, _ in service.tasks() if ref.kind == "factor"]) == 1
    button(research, "运行因子研究").click().run()
    assert not research.exception and len(service.tasks()) == 2
    reopened = page(service.root, "research")
    assert not reopened.exception
    assert any("0.0200%" in v.value for v in reopened.markdown)
    # Editing parameters never starts a new fit/run and invalidates the previous check.
    research.number_input[0].set_value(0.90)
    button(research, "运行因子研究").click().run()
    assert research.error and not research.exception
    assert len(service.tasks()) == 2


def test_workspace_switch_clears_drafts_and_result_references(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    DeskService(first).create()
    DeskService(second).create()
    monkeypatch.setenv("PRD_GUI_WORKSPACE", str(first))
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    button(app, "打开工作区").click().run()
    app.session_state.desk_check_factor = "old-approval"
    app.session_state.desk_history_reference = "another-workspace"
    app.text_input[0].set_value(str(second))
    button(app, "打开工作区").click().run()
    assert not app.exception
    assert app.session_state.desk_root == str(second.resolve())
    assert "desk_check_factor" not in app.session_state
    assert "desk_history_reference" not in app.session_state
