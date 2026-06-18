"""V4.9.1 temporary hotspot/clickable-button disablement tests.

User request: Outlook still shows slice seams after cutting; hide the
"添加可点击按钮" feature first so normal send/copy paths do not enter hotspot
physical slicing while the seam root cause is investigated.
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


def test_hotspot_feature_flag_is_disabled():
    assert HOTSPOT_FEATURE_ENABLED is False


def test_hidden_hotspot_button_and_plain_slice_path_ignore_existing_hotspots(qapp, tmp_path):
    src = tmp_path / "slice_001.png"
    Image.new("RGB", (650, 80), "white").save(src)

    win = MainWindow()
    try:
        win.slice_paths = [str(src)]
        win.slice_source_index = {os.path.basename(src): 1.0}
        # Simulate stale data from older sessions/paths. V4.9.1 must ignore it.
        win.hotspot_map.add(os.path.basename(src), Hotspot(10, 10, 120, 50, "https://example.com"))

        assert not win.btn_hotspot.isVisible()

        items = win._build_slices_with_hotspots()

        assert len(items) == 1
        assert items[0].path == str(src)
        assert items[0].href is None
        assert items[0].sort_key == 1.0
    finally:
        win.close()


def test_thumbnail_has_no_hotspot_click_handler_when_disabled(qapp, tmp_path):
    src = tmp_path / "slice_001.png"
    Image.new("RGB", (650, 80), "white").save(src)

    win = MainWindow()
    try:
        win._show_thumbnails([str(src)])

        wrapper = win.thumb_grid.itemAt(0).widget()
        assert wrapper.toolTip() == f"切片 1: {src.name}"
        # No per-instance mousePressEvent override should be installed when disabled.
        assert "mousePressEvent" not in wrapper.__dict__
    finally:
        win.close()
