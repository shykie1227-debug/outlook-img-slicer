from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from clickable_map import Hotspot, HotspotMap


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_main_window_send_preflight_blocks_invalid_saved_hotspot(qapp, tmp_path):
    import main

    image_path = tmp_path / "slice.png"
    Image.new("RGB", (300, 200), "white").save(image_path)
    win = main.MainWindow()
    try:
        win.slice_paths = [str(image_path)]
        win.hotspot_map._map[image_path.name] = [
            Hotspot(250, 20, 350, 100, "https://outside.example")
        ]

        ok, reason = win._validate_hotspots_before_output()

        assert not ok
        assert "越界" in reason
    finally:
        win.close()


def test_hotspot_map_rejects_real_rectangle_overlap():
    hotspot_map = HotspotMap()
    ok, reason = hotspot_map.add(
        "slice.png", Hotspot(20, 20, 180, 100, "https://one.example")
    )
    assert ok, reason

    ok, reason = hotspot_map.add(
        "slice.png", Hotspot(120, 60, 240, 140, "https://two.example")
    )

    assert not ok
    assert "重叠" in reason


def test_hotspot_map_rejects_unsupported_url_schemes():
    hotspot_map = HotspotMap()

    for url in ("javascript:alert(1)", "ftp://example.com/file", "file:///C:/test"):
        ok, reason = hotspot_map.add("slice.png", Hotspot(10, 10, 80, 40, url))
        assert not ok
        assert "http" in reason.lower()


def test_hotspot_map_preflight_checks_image_bounds(tmp_path):
    image_path = tmp_path / "slice.png"
    Image.new("RGB", (300, 200), "white").save(image_path)
    hotspot_map = HotspotMap()
    hotspot_map._map[image_path.name] = [
        Hotspot(250, 20, 350, 100, "https://outside.example")
    ]

    ok, reason = hotspot_map.validate_for_images([str(image_path)])

    assert not ok
    assert "越界" in reason


def test_hotspot_map_preflight_accepts_many_non_overlapping_buttons(tmp_path):
    image_path = tmp_path / "slice.png"
    Image.new("RGB", (600, 400), "white").save(image_path)
    hotspot_map = HotspotMap()
    for hotspot in (
        Hotspot(20, 20, 150, 80, "https://one.example"),
        Hotspot(220, 20, 350, 80, "https://two.example"),
        Hotspot(80, 180, 260, 250, "https://three.example"),
        Hotspot(360, 290, 580, 370, "https://four.example"),
    ):
        ok, reason = hotspot_map.add(image_path.name, hotspot)
        assert ok, reason

    ok, reason = hotspot_map.validate_for_images([str(image_path)])

    assert ok, reason
    assert hotspot_map.total_count() == 4
