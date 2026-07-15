import re
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

import main
import outlook_sender
import html_assembler
from html_assembler import SliceItem, assemble_html


ROOT = Path(__file__).resolve().parent.parent
DESKTOP_ROOT = ROOT / "desktop"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_v630_version_is_synchronized_everywhere():
    version_info = (DESKTOP_ROOT / "version_info.txt").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    spec = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    assert main.VERSION == "6.3.0"
    assert "6.3.0.20260715" in version_info
    assert "u'040904B0'" in version_info
    assert "VarFileInfo" in version_info
    assert "0x0409, 1200" in version_info
    version_tuple = re.search(r"filevers=\(([^)]+)\)", version_info)
    assert version_tuple
    components = [int(value.strip()) for value in version_tuple.group(1).split(",")]
    assert components == [6, 3, 0, 2026]
    assert all(0 <= value <= 65535 for value in components)
    assert "OutlookImgSlicer-V6.3.0.exe" in readme
    assert "V6.3.0" in spec


def test_main_window_exposes_three_workflow_steps(qapp):
    win = main.MainWindow()
    try:
        assert win.step_import.title == "1  放入文件"
        assert win.step_edit.title == "2  编辑切片与链接"
        assert win.step_output.title == "3  检查并输出"
        assert "background" in win.page_scroll.styleSheet()
        win.show()
        qapp.processEvents()
        assert win.header_title.height() > 0
        assert win.header_subtitle.height() > 0
        assert win.guide_label.height() > 0
    finally:
        win.close()


def test_toolbar_reflows_at_minimum_width(qapp):
    win = main.MainWindow()
    try:
        win.resize(620, 760)
        win._apply_responsive_layout(620)
        # Settings now use QHBoxLayout (always single row by definition)
        assert win.settings_container.layout().count() >= 4

        narrow_output_rows = {
            win.output_grid.getItemPosition(index)[0]
            for index in range(win.output_grid.count())
        }

        win.resize(1100, 760)
        win._apply_responsive_layout(1100)
        wide_output_rows = {
            win.output_grid.getItemPosition(index)[0]
            for index in range(win.output_grid.count())
        }

        assert len(narrow_output_rows) == 1
        assert len(wide_output_rows) == 1
    finally:
        win.close()


def test_minimum_window_does_not_overlap_import_controls(qapp):
    win = main.MainWindow()
    try:
        win.resize(620, 760)
        win.show()
        qapp.processEvents()

        assert win.drop_zone.geometry().bottom() < win.settings_container.geometry().top()
    finally:
        win.close()


def test_render_plan_records_physical_and_display_geometry(tmp_path):
    path = tmp_path / "slice.png"
    Image.new("RGB", (648, 120), "white").save(path)

    assert hasattr(html_assembler, "build_render_plan")
    plan = html_assembler.build_render_plan([SliceItem(path=str(path), sort_key=1.0)], 648)

    assert len(plan.items) == 1
    item = plan.items[0]
    assert item.physical_width == 648
    assert item.physical_height == 120
    assert item.display_width == 648
    assert item.display_height == 120
    assert item.cid == "slice_001"


def test_plain_render_plan_preserves_non_multiple_of_four_width(tmp_path):
    path = tmp_path / "plain-650.png"
    Image.new("RGB", (650, 121), "white").save(path)

    plan = html_assembler.build_render_plan(
        [SliceItem(path=str(path), sort_key=1.0)], 650
    )

    assert plan.display_width == 650
    assert plan.items[0].display_width == 650
    assert plan.items[0].display_height == 121


def test_outlook_html_declares_96_pixels_per_inch(tmp_path):
    path = tmp_path / "slice.png"
    Image.new("RGB", (648, 120), "white").save(path)

    html = assemble_html([SliceItem(path=str(path), sort_key=1.0)], 648)

    assert 'xmlns:v="urn:schemas-microsoft-com:vml"' in html
    assert "<o:PixelsPerInch>96</o:PixelsPerInch>" in html
    assert "<o:AllowPNG/>" in html


def test_outlook_attachments_use_render_plan_cids(tmp_path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (648, 100), "white").save(first)
    Image.new("RGB", (648, 100), "white").save(second)
    plan = html_assembler.build_render_plan([
        SliceItem(path=str(second), sort_key=2.0),
        SliceItem(path=str(first), sort_key=1.0),
    ], 648)

    assert hasattr(outlook_sender, "resolve_attachment_manifest")
    manifest = outlook_sender.resolve_attachment_manifest(render_plan=plan)

    assert manifest == [
        (str(first), "slice_001"),
        (str(second), "slice_002"),
    ]
