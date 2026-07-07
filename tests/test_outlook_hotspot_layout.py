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


def test_hotspot_rows_do_not_share_or_nest_table_columns(tmp_path):
    prepared = _prepared_hotspot_items(tmp_path)
    html = assemble_html(prepared, 648)

    # Fix 1-A: 所有行放入「1 个内层 table」+ 外层 wrapper table = 2 个 table；
    # 不再有每行独立 table（消除表间 1px 缝），也不再使用 <div>。
    assert html.count("<table") == 2
    assert html.count("<div") == 0
    # 单表内每行一个 <tr height>，且 <tr height> 与 <td height> 一致（修复纵向错位）
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
