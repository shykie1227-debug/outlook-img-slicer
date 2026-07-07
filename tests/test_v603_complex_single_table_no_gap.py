"""
V6.0.3 修复 1-C 回归测试：hotspot / 多段链路统一为「单 <table> + 每行一个 <tr>」

覆盖 Fix 1-A（单表结构消除表间 1px 缝）+ Fix 1-B（非普通链路先 materialize，
保证 PNG 物理尺寸与 HTML 声明严格一致）：

  1. CID 模式（assemble_html）产出的 <table> 数量 == 2（外层 wrapper + 1 个内层单表），
     不再有「每行独立 <table>」（修复前为 N+1 个 → 表间 1px 缝）。
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


def _cid_sequence(html: str):
    return re.findall(r'cid:(slice_\d+)', html)


def test_cid_assemble_produces_single_inner_table(tmp_path):
    """Fix 1-A：hotspot 链路 CID 模式只生成 1 个内层 table（+ 外层 wrapper = 2）。"""
    slices = _build_complex_slices(tmp_path)
    html = assemble_html(slices, 960)

    # 外层 wrapper + 1 个内层单表 = 2 个 <table>
    assert html.count("<table") == 2, f"期望 2 个 table，实际 {html.count('<table')}"
    assert html.count("<div") == 0


def test_cid_assemble_tr_height_matches_td_height(tmp_path):
    """Fix 1-A：每个 <tr height> 与其内部所有 <td height> 严格相等（无纵向错位）。"""
    slices = _build_complex_slices(tmp_path)
    html = assemble_html(slices, 960)

    blocks = _tr_blocks(html)
    # 至少有 1 个内层 <tr>（不含外层 wrapper 的 <tr>，外层无 height 属性）
    inner_blocks = [b for b in blocks if b[0] is not None]
    assert inner_blocks, "未找到带 height 的内层 <tr>"
    for tr_height, cells in inner_blocks:
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

    blocks = _tr_blocks(html)
    inner_blocks = [b for b in blocks if b[0] is not None]
    for tr_height, cells in inner_blocks:
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


def test_base64_generate_plain_html_is_single_table_with_base64(tmp_path):
    """Fix 1-A + Fix 2-A：复制（base64）模式同样是单表结构且自包含内联图片。"""
    slices = _build_complex_slices(tmp_path)
    html = generate_plain_html(slices, 960)

    assert html.count("<table") == 2
    # 网页邮箱路径：base64 内联，无 cid 引用
    assert "data:image/" in html and ";base64," in html
    assert "cid:" not in html
    # 链接保留
    assert "https://top.example" in html
    assert "https://bottom.example" in html
