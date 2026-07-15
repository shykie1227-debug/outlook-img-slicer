from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_code_agent_guide_matches_current_desktop_architecture():
    """Agent 指引必须描述当前 PySide 桌面架构，不能继续指向旧前端树。"""
    guide = (ROOT / "CODE-AGENT-GUIDE.md").read_text(encoding="utf-8")

    required_sections = [
        "必读文档指引",
        "配色/字号/按钮速查表",
        "CRITICAL 图标规则和禁止事项",
        "项目结构和文件说明",
        "CSS 类命名约定",
        "提交前的检查清单",
    ]
    for section in required_sections:
        assert section in guide

    for current_path in [
        "DESIGN.md",
        "SPEC.md",
        "desktop/main.py",
        "desktop/build.py",
        "html_assembler.py",
        "outlook_sender.py",
        "icon.ico",
        "icons/",
    ]:
        assert current_path in guide

    assert "稳定 V6/PySide" in guide

    stale_markers = [
        "app/src",
        "legacy/v5-python-ui",
        "Zustand",
        "npx vitest",
    ]
    for marker in stale_markers:
        assert marker not in guide


def test_spec_matches_current_desktop_architecture():
    """SPEC 应作为当前产品规格，不应保留已废弃的目录结构。"""
    spec = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert "V6.3.0" in spec
    assert "稳定 V6/PySide" in spec
    assert "desktop/main.py" in spec
    assert "icon.ico" in spec
    assert "html_assembler.py" in spec
    assert "outlook_sender.py" in spec
    assert "mail.Display(False)" in spec
    assert "mail.Send()" in spec

    stale_markers = [
        "ui/main_window.py",
        "core/image_slicer.py",
        "outlook_inserter.py",
        "版本: v5.0.0.20260629",
    ]
    for marker in stale_markers:
        assert marker not in spec
