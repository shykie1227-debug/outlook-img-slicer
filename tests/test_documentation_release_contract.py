from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_handoff_describes_internal_and_release_build_artifacts():
    handoff = _read("HANDOFF.md")

    assert "desktop/dist/OutlookImgSlicer.exe" in handoff
    assert "dist/OutlookImgSlicer-V6.3.0.exe" in handoff
    assert "build-manifest.json" in handoff
    assert "166 passed, 0 failed" in handoff
    assert "# 166 passed" in handoff
    assert "2026-07-15" in handoff
    assert "999px" not in handoff


def test_design_matches_current_main_window_labels_and_layout():
    design = _read("DESIGN.md")

    assert "复制图片（兼容方式）" in design
    assert "邮件品质下拉" in design
    assert "默认宽度：760px" in design
    assert "最大宽度：760px" not in design


def test_test_plan_uses_current_release_contract():
    test_plan = _read("TEST_PLAN.md")

    assert "V6.3.0" in test_plan
    assert "python3 -m pytest tests/ -q" in test_plan
    assert "80–1200px" in test_plan
    assert "V5.0 当前 93 项" not in test_plan
    assert "EXE 构建由用户本地完成" not in test_plan
    assert "mail.Send()" in test_plan


def test_readme_and_ui_preview_match_supported_desktop_features():
    readme = _read("README.md")
    preview = _read("desktop/ui-preview.html")

    assert "BMP / SVG / PDF" not in readme
    assert "发送图片质量：" in preview
    assert "自动（超过 20MB 时询问）" in preview
    assert "flex-wrap: nowrap" in preview
