from pathlib import Path

from PIL import Image
import pytest
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from clickable_map import Hotspot, HotspotMap
from cut_editor import CutEditorDialog
from export_dialog import ExportFormatDialog
from hotspot_editor import HotspotEditorDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _assert_dialog_scales(dialog, qapp, wide_width: int):
    dialog.show()
    qapp.processEvents()
    label = next(widget for widget in dialog.findChildren(QLabel) if widget.font().pointSizeF() > 0)
    label_baseline = label.font().pointSizeF()
    root_style_baseline = dialog.styleSheet()
    item_font_baseline = None
    if hasattr(dialog, "list_widget") and dialog.list_widget.count():
        item_font_baseline = dialog.list_widget.item(0).font().pointSizeF()

    dialog.resize(wide_width, dialog.height())
    qapp.processEvents()

    assert label.font().pointSizeF() > label_baseline
    if root_style_baseline and "px" in root_style_baseline:
        assert dialog.styleSheet() != root_style_baseline
    if item_font_baseline is not None:
        assert dialog.list_widget.item(0).font().pointSizeF() > item_font_baseline
    assert "999px" not in dialog.styleSheet()
    assert all("999px" not in widget.styleSheet() for widget in dialog.findChildren(QWidget))


def test_all_edit_dialogs_follow_window_scale_and_use_real_radii(qapp, tmp_path: Path):
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (320, 180), "white").save(first)
    Image.new("RGB", (320, 180), "white").save(second)

    hotspot_map = HotspotMap()
    hotspot_map.add(first.name, Hotspot(10, 10, 100, 50, "https://example.com"))
    dialogs = [
        ExportFormatDialog([str(first)]),
        CutEditorDialog([str(first), str(second)]),
        HotspotEditorDialog(str(first), hotspot_map),
    ]
    try:
        for dialog in dialogs:
            reference_width = dialog._scale_reference_width
            _assert_dialog_scales(dialog, qapp, round(reference_width * 1.35))
    finally:
        for dialog in dialogs:
            dialog.close()
