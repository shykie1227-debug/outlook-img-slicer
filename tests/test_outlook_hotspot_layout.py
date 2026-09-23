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

    # V6.4.0 结构性根修：整封邮件只有 1 张 table、1 条 <tr>，没有嵌套表格。
    # 旧结构（每视觉行一条 <tr>）会让 Word 引擎在行间插入约 1px 间距，
    # 一封 3 按钮邮件实测 9 条 <tr> → 8 处缝隙。
    assert html.count("<table") == 1
    assert html.count("<tr") == 1
    assert html.count('data-layout="hotspot-grid"') == 1
    assert 'data-layout="hotspot-row"' not in html
    assert html.count("<div") == 0
    assert html.count("<colgroup") == 0
    assert html.count("colspan") == 0
    assert "table-layout: fixed" in html

    cells = re.findall(
        r'<td align="left" valign="top" width="(\d+)" '
        r'style="width: \d+px; height: (\d+)px;',
        html,
    )
    assert len(cells) > 1, "热点邮件应按 X 列拆成多个 <td>"
    col_widths = [int(width) for width, _height in cells]
    assert sum(col_widths) == 648
    # 每列内的 <img> 宽度必须与该列 <td> 宽度一致（横向不错位）
    for match in re.finditer(
        r'<td align="left" valign="top" width="(\d+)"[^>]*>(.*?)</td>', html, re.DOTALL
    ):
        td_width = int(match.group(1))
        inner = match.group(2)
        img_widths = [int(w) for w in re.findall(r'<img[^>]*?width="(\d+)"', inner)]
        assert img_widths, "每个列 <td> 至少要有一张 <img>"
        assert all(width == td_width for width in img_widths)


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
