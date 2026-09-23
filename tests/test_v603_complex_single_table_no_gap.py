"""
Hotspot / 多段链路回归测试：单行列网格（V6.4.0 结构性根修）。

历史背景：
  V6.0.3 用「单表 + 每视觉行一条 <tr> + colgroup/colspan」消除了表间缝隙，
  但 Outlook Word 引擎在 <tr> 之间始终插入约 1px 间距（见 html_assembler
  模块 docstring V4.9.0），行数越多缝隙越多 —— 一封 3 按钮邮件实测 9 条 <tr>，
  用户表现为"添加可点击按钮后出现各种缝隙"。

V6.4.0 根修后的结构契约：
  1. 整封邮件只有 1 张 <table>、1 条 <tr>，没有任何嵌套表格。
  2. 每个 X 列一个 <td>，列内 display:block 连续堆叠该列的竖向片段
     （与普通长图 _build_v3_plain_image_stack 同一套写法）。
  3. 各 <td> width 之和 == 邮件宽度；每个 <td> 内 <img> 宽度 == 该 <td> 宽度；
     每个 <td> 内 <img> 高度之和 == 该 <td> 高度。
  4. HTML 里的 cid: 引用集合与 outlook_sender/resolve_attachment_manifest
     的附件 CID 完全一致、无重复、各出现一次（列优先顺序）。
  5. base64 模式（generate_plain_html）同样为单表单行结构且内嵌 data:image。
"""
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clickable_map import Hotspot
from hotspot_slicer import slice_paths_by_hotspots
from html_assembler import (
    SliceItem,
    assemble_html,
    build_render_plan,
    generate_plain_html,
    materialize_display_slices_strict,
)


def _build_complex_slices(tmp_path: Path) -> list[SliceItem]:
    """构造 1 张原图 + 2 个上下错开、不同列的 hotspot（触发多行多列网格）。"""
    src = tmp_path / "grid.png"
    Image.new("RGB", (1000, 1000), (20, 80, 160)).save(src)
    hotspots = {
        src.name: [
            Hotspot(100, 100, 400, 500, "https://top.example"),
            Hotspot(600, 600, 900, 900, "https://bottom.example"),
        ]
    }
    sliced, link_map = slice_paths_by_hotspots(
        [str(src)], hotspots, source_index_map={src.name: 1.0}
    )
    return [
        SliceItem(
            path=path,
            href=link_map.get(Path(path).name),
            sort_key=sort_key,
            original_width=1000,
        )
        for path, sort_key in sliced
    ]


def _outer_width(html: str) -> int:
    m = re.search(r'<table[^>]*?width="(\d+)"', html)
    return int(m.group(1))


def _column_cells(html: str):
    """返回 [(td_width, td_height, [(img_width, img_height), ...]), ...]，按 HTML 顺序。"""
    cells = []
    for match in re.finditer(
        r'<td align="left" valign="top" width="(\d+)" '
        r'style="width: \d+px; height: (\d+)px;(.*?)</td>',
        html,
        re.DOTALL,
    ):
        td_width, td_height, inner = int(match.group(1)), int(match.group(2)), match.group(3)
        images = [
            (int(w), int(h))
            for w, h in re.findall(r'<img[^>]*?width="(\d+)"[^>]*?height="(\d+)"', inner)
        ]
        cells.append((td_width, td_height, images))
    return cells


def _cid_sequence(html: str):
    return re.findall(r'cid:(slice_\d+)', html)


def test_cid_assemble_is_a_single_table_with_a_single_row(tmp_path):
    """结构根修：1 张表、1 条 <tr>，无嵌套表格、无 colgroup/colspan。"""
    slices = _build_complex_slices(tmp_path)
    html = assemble_html(slices, 960)

    assert html.count("<table") == 1, "不允许嵌套表格（Word 引擎会在嵌套边界产生缝隙）"
    assert html.count("<tr") == 1, "行间 1px 缝的根因就是多条 <tr>，必须只有 1 条"
    assert html.count('data-layout="hotspot-grid"') == 1
    assert "<colgroup" not in html
    assert "colspan" not in html
    assert html.count("<div") == 0
    assert "table-layout: fixed" in html


def test_cid_assemble_columns_tile_the_display_width(tmp_path):
    """每个 <td> 内 <img> 宽度 == <td> 宽度，且各 <td> 宽度之和 == 邮件宽度。"""
    slices = _build_complex_slices(tmp_path)
    html = assemble_html(slices, 960)
    outer_w = _outer_width(html)

    cells = _column_cells(html)
    assert len(cells) > 1, "热点邮件应按 X 列拆成多个 <td>"
    assert sum(td_width for td_width, _h, _imgs in cells) == outer_w
    for td_width, _td_height, images in cells:
        assert images, "每个列 <td> 至少要有一张 <img>"
        assert all(img_w == td_width for img_w, _img_h in images), (
            f"<td width={td_width}> 内出现了宽度不一致的 <img> → 横向错位"
        )


def test_cid_assemble_column_stacks_sum_to_the_cell_height(tmp_path):
    """每个 <td> 内 <img> 高度之和 == 该 <td> 高度 → 纵向无空隙、无溢出。"""
    slices = _build_complex_slices(tmp_path)
    html = assemble_html(slices, 960)

    for td_width, td_height, images in _column_cells(html):
        stacked = sum(img_h for _img_w, img_h in images)
        assert stacked == td_height, (
            f"<td width={td_width}> 内 <img> 高度和 {stacked} != <td> 高度 {td_height}"
        )
        for _img_w, img_h in images:
            assert img_h % 4 == 0, f"<img height={img_h}> 不是 4 的倍数（Word pt 取整会出白线）"


def test_cid_assemble_cid_set_matches_the_attachment_manifest(tmp_path):
    """HTML 的 cid 集合 == build_render_plan 的附件 CID，无重复、各出现一次。

    复刻 desktop/main.py 的真实发送顺序：先 materialize → 再 build_render_plan →
    再 assemble_html(prepared=True)。
    """
    slices = _build_complex_slices(tmp_path)
    prepared = materialize_display_slices_strict(slices, 960)
    html = assemble_html(prepared, 960, prepared=True)
    plan = build_render_plan(prepared, 960)

    expected = [item.cid for item in plan.items]
    actual = _cid_sequence(html)

    assert sorted(actual) == sorted(expected), (
        f"cid 集合漂移：\nHTML {sorted(actual)}\n附件 {sorted(expected)}"
    )
    assert len(set(actual)) == len(actual), "同一个 cid 在正文里重复出现会导致图片错乱"
    assert len(actual) == html.count("<img"), "每个 <img> 都必须对应一个附件 CID"


def test_base64_generate_plain_html_uses_single_row_grid_with_base64(tmp_path):
    """复制模式使用相同单行网格，并保持自包含内联图片。"""
    slices = _build_complex_slices(tmp_path)
    html = generate_plain_html(slices, 960)

    assert html.count("<table") == 1
    assert html.count("<tr") == 1
    assert html.count('data-layout="hotspot-grid"') == 1
    assert "<colgroup" not in html and "colspan" not in html
    # 网页邮箱路径：base64 内联，无 cid 引用
    assert "data:image/" in html and ";base64," in html
    assert "cid:" not in html
    # 链接保留
    assert "https://top.example" in html
    assert "https://bottom.example" in html
