"""
Hotspot / 多段链路回归测试：单表统一列网格。

覆盖 Fix 1-A（单表结构消除表间 1px 缝）+ Fix 1-B（非普通链路先 materialize，
保证 PNG 物理尺寸与 HTML 声明严格一致）：

  1. CID 模式使用一个统一热区表格，通过 colgroup/colspan 容纳不同 X 边界。
  2. 每个 <tr height="H"> 内所有 <td height> 都 == H（纵向不再错位）。
  3. 同一 <tr> 内所有 <td width> 之和 == 外层显示宽度（横向不再错位/换行）。
  4. CID 模式下 slice_XXX 的计数与顺序，与 outlook_sender.create_email_with_images
     的 enumerate(sorted(slices, key=sort_key)) 完全一致（materialize 后顺序不漂移）。
  5. base64 模式（generate_plain_html）同样为单表结构且内嵌 data:image base64。
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
    generate_plain_html,
)


def _build_complex_slices(tmp_path: Path) -> list[SliceItem]:
    """构造 1 张原图 + 2 个上下错开、不同列的 hotspot（触发 V2 网格多行多列）。"""
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


def _tr_blocks(html: str):
    """返回 [(tr_height, [(td_width, td_height), ...]), ...]"""
    blocks = []
    for tr in re.findall(r'<tr[^>]*?(?: height="(\d+)")?[^>]*>(.*?)</tr>', html, re.DOTALL):
        tr_height = int(tr[0]) if tr[0] else None
        inner = tr[1]
        cells = [
            (int(w), int(h)) for w, h in re.findall(
                r'<td[^>]*?width="(\d+)"[^>]*?height="(\d+)"', inner
            )
        ]
        blocks.append((tr_height, cells))
    return blocks


def _hotspot_grid(html: str):
    match = re.search(
        r'<table[^>]*data-layout="hotspot-grid"[^>]*>(.*?)</table>',
        html,
        re.DOTALL,
    )
    assert match, "未找到统一热区网格"
    return match.group(1)


def _cid_sequence(html: str):
    return re.findall(r'cid:(slice_\d+)', html)


def test_cid_assemble_uses_one_unified_column_grid(tmp_path):
    """所有热区行共享同一列定义，不嵌套会产生 Outlook 缝隙的行表格。"""
    slices = _build_complex_slices(tmp_path)
    html = assemble_html(slices, 960)

    assert html.count("<table") == 2
    assert html.count('data-layout="hotspot-grid"') == 1
    assert 'data-layout="hotspot-row"' not in html
    assert len(_tr_blocks(_hotspot_grid(html))) == 5
    assert html.count("<div") == 0


def test_cid_assemble_tr_height_matches_td_height(tmp_path):
    """Fix 1-A：每个 <tr height> 与其内部所有 <td height> 严格相等（无纵向错位）。"""
    slices = _build_complex_slices(tmp_path)
    html = assemble_html(slices, 960)

    blocks = _tr_blocks(_hotspot_grid(html))
    assert blocks, "统一热区网格应包含视觉行"
    for tr_height, cells in blocks:
        assert cells, "内层 <tr> 应至少含 1 个 <td>"
        for td_w, td_h in cells:
            assert td_h == tr_height, (
                f"<td height={td_h}> 与 <tr height={tr_height}> 不一致 → 纵向错位"
            )


def test_cid_assemble_row_width_sums_to_display_width(tmp_path):
    """Fix 1-A：同一 <tr> 内所有 <td width> 之和 == 外层显示宽度（无横向错位/换行）。"""
    slices = _build_complex_slices(tmp_path)
    html = assemble_html(slices, 960)
    outer_w = _outer_width(html)

    for tr_height, cells in _tr_blocks(_hotspot_grid(html)):
        row_sum = sum(td_w for td_w, _ in cells)
        assert row_sum == outer_w, (
            f"一行 <td width> 之和 {row_sum} != 外层宽度 {outer_w} → 横向错位"
        )


def test_cid_assemble_cid_order_matches_sorted_slices(tmp_path):
    """Fix 1-B：materialize 后 cid 顺序与 outlook_sender 的 enumerate(sorted) 一致。"""
    slices = _build_complex_slices(tmp_path)
    html = assemble_html(slices, 960)

    expected = [
        f"slice_{i + 1:03d}" for i in range(len(slices))
    ]
    actual = _cid_sequence(html)
    assert actual == expected, (
        f"cid 顺序漂移：\n预期 {expected}\n实际 {actual}"
    )


def test_base64_generate_plain_html_uses_unified_grid_with_base64(tmp_path):
    """复制模式使用相同统一网格，并保持自包含内联图片。"""
    slices = _build_complex_slices(tmp_path)
    html = generate_plain_html(slices, 960)

    assert html.count('data-layout="hotspot-grid"') == 1
    assert 'data-layout="hotspot-row"' not in html
    assert len(_tr_blocks(_hotspot_grid(html))) == 5
    # 网页邮箱路径：base64 内联，无 cid 引用
    assert "data:image/" in html and ";base64," in html
    assert "cid:" not in html
    # 链接保留
    assert "https://top.example" in html
    assert "https://bottom.example" in html
