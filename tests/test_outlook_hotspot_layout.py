from pathlib import Path
import re

from PIL import Image

from clickable_map import Hotspot
from hotspot_slicer import slice_paths_by_hotspots
from html_assembler import (
    SliceItem,
    _group_by_source,
    assemble_html,
    materialize_display_slices_strict,
)


def _prepared_hotspot_items(tmp_path: Path) -> list[SliceItem]:
    source = tmp_path / "long.png"
    Image.new("RGB", (650, 600), "white").save(source)
    hotspots = {
        source.name: [
            Hotspot(60, 80, 210, 150, "https://top.example"),
            Hotspot(410, 420, 590, 500, "https://bottom.example"),
        ]
    }
    sliced, links = slice_paths_by_hotspots(
        [str(source)],
        hotspots,
        source_index_map={source.name: 1.0},
    )
    raw = [
        SliceItem(
            path=path,
            href=links.get(Path(path).name),
            sort_key=sort_key,
            original_width=650,
        )
        for path, sort_key in sliced
    ]
    return materialize_display_slices_strict(raw, 648)


def test_hotspot_rows_share_one_unified_column_grid(tmp_path):
    prepared = _prepared_hotspot_items(tmp_path)
    html = assemble_html(prepared, 648)

    # 外层居中 table + 一个统一热区 table。不能再为每个视觉行嵌套 table，
    # 否则 Outlook Word 会在嵌套表边界重新计算行高并产生可见缝隙。
    assert html.count("<table") == 2
    assert html.count('data-layout="hotspot-grid"') == 1
    assert 'data-layout="hotspot-row"' not in html
    assert html.count("<div") == 0
    assert "table-layout: fixed" in html
    assert "<tr height=" in html

    col_widths = [
        int(width)
        for width in re.findall(r'<col width="(\d+)"', html)
    ]
    assert len(col_widths) > 1
    assert sum(col_widths) == 648

    grid = re.search(
        r'<table[^>]*data-layout="hotspot-grid"[^>]*>(.*?)</table>',
        html,
        re.DOTALL,
    ).group(1)
    visual_rows = re.findall(r'<tr height="\d+"[^>]*>(.*?)</tr>', grid, re.DOTALL)
    assert len(visual_rows) == 5
    for row in visual_rows:
        spans = []
        for tag in re.findall(r'<td[^>]*>', row):
            match = re.search(r'colspan="(\d+)"', tag)
            spans.append(int(match.group(1)) if match else 1)
        assert sum(spans) == len(col_widths)


def test_hotspot_links_are_inline_while_images_remain_block(tmp_path):
    prepared = _prepared_hotspot_items(tmp_path)
    html = assemble_html(prepared, 648)

    assert "https://top.example" in html
    assert "https://bottom.example" in html
    # Fix 1-A / Fix 2-C: 不再使用 inline-block <span>（_build_inline_segment 已删除），
    # 链接 <a> 与图片 <img> 都用 display: block（Outlook Word 引擎稳定零缝）。
    assert "<a " in html
    assert "<img" in html
    assert "display: block" in html
    # 确认废弃的 inline-block 方案已彻底移除
    assert "display: inline-block" not in html
