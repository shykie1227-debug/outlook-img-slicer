"""V4.8.11 hotspot grid V2 regression tests.

目标：上下不同位置的按钮可以横向范围重叠；导出仍按视觉网格还原长图。
"""
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clickable_map import Hotspot
from hotspot_slicer import slice_paths_by_hotspots, validate_hotspots_no_overlap
from html_assembler import SliceItem, materialize_display_slices, assemble_html


def test_stacked_hotspots_with_same_x_range_are_allowed():
    hotspots = [
        Hotspot(100, 100, 250, 180, "https://top.example"),
        Hotspot(100, 300, 250, 380, "https://bottom.example"),
    ]

    ok, reason = validate_hotspots_no_overlap(hotspots, 650, 500)
    assert ok, reason


def test_hotspot_grid_v2_keeps_rows_separate_and_links_both_buttons(tmp_path):
    src = tmp_path / "grid.png"
    Image.new("RGB", (650, 500), (20, 80, 160)).save(src)
    hotspots = {
        "grid.png": [
            Hotspot(100, 100, 250, 180, "https://top.example"),
            Hotspot(100, 300, 250, 380, "https://bottom.example"),
        ]
    }

    sliced, link_map = slice_paths_by_hotspots(
        [str(src)], hotspots, source_index_map={"grid.png": 1.0}
    )
    # X lines: 0,100,250,650 => 3 cols; Y lines: 0,100,180,300,380,500 => 5 rows
    assert len(sliced) == 15
    assert sum(1 for name in link_map if link_map[name]) == 2

    slices = [
        SliceItem(
            path=path,
            href=link_map.get(Path(path).name),
            sort_key=sort_key,
            original_width=650,
        )
        for path, sort_key in sliced
    ]
    prepared = materialize_display_slices(slices, 650)
    html = assemble_html(prepared, 650)

    assert "https://top.example" in html
    assert "https://bottom.example" in html
    # V2 必须输出多行，而不是把 15 个 cell 横向塞进单行。
    assert len(re.findall(r"<tr height=", html)) >= 5
    # V4.9.4: hotspot rows share one inner table instead of one div/table wrapper per row.
    assert html.count("<div") == 0
    assert html.count("<table") == 2

    # 所有预渲染 PNG 边缘不得出现默认黑/白异常色。
    for item in prepared:
        with Image.open(item.path) as out:
            assert out.getpixel((0, 0)) == (20, 80, 160)
            assert out.getpixel((out.width - 1, out.height - 1)) == (20, 80, 160)
