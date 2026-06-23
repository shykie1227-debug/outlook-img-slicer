"""V4.9.4 hotspot/clickable-button re-enable tests.

User request: bring back clickable buttons while keeping the no-seam Outlook
path. Hotspots should be available in the UI and should enter the physical
slicing path only when the user actually added button areas.
"""

import os

import pytest
from PIL import Image

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from clickable_map import Hotspot
from main import HOTSPOT_FEATURE_ENABLED, MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_hotspot_feature_flag_is_enabled():
    assert HOTSPOT_FEATURE_ENABLED is True


def test_hotspot_button_visible_and_existing_hotspots_are_applied(qapp, tmp_path):
    src = tmp_path / "slice_001.png"
    Image.new("RGB", (650, 80), "white").save(src)

    win = MainWindow()
    try:
        win.slice_paths = [str(src)]
        win.slice_source_index = {os.path.basename(src): 1.0}
        win.hotspot_map.add(os.path.basename(src), Hotspot(10, 10, 120, 50, "https://example.com"))

        assert not win.btn_hotspot.isHidden()

        items = win._build_slices_with_hotspots()

        assert len(items) > 1
        assert any(item.href == "https://example.com" for item in items)
        assert all(item.sort_key >= 1.0 for item in items)
    finally:
        win.close()


def test_thumbnail_has_hotspot_click_handler_when_enabled(qapp, tmp_path):
    src = tmp_path / "slice_001.png"
    Image.new("RGB", (650, 80), "white").save(src)

    win = MainWindow()
    try:
        win._show_thumbnails([str(src)])

        wrapper = win.thumb_grid.itemAt(0).widget()
        assert "点击可添加/编辑可点击按钮" in wrapper.toolTip()
        assert "mousePressEvent" in wrapper.__dict__
    finally:
        win.close()
