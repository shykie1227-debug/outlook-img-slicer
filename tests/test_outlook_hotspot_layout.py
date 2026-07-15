from pathlib import Path

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


def test_hotspot_rows_use_independent_nested_column_grids(tmp_path):
    prepared = _prepared_hotspot_items(tmp_path)
    html = assemble_html(prepared, 648)

    # 一个连续 stack 管纵向，每行自己的单行表格管理不同的 X 边界。
    assert html.count('data-layout="hotspot-stack"') == 1
    assert html.count('data-layout="hotspot-row"') == 5
    assert html.count("<div") == 0
    assert "table-layout: fixed" in html
    assert "<tr height=" in html


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
