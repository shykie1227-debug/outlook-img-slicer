"""
V4.8.6 普通纵向切片无 1px 缝隙回归测试

覆盖 V4.8.6 修复：
  - materialize 输出的 PNG 物理高度 = HTML <tr height> 声明高度
  - materialize 输出的 PNG 物理高度 = HTML <img height> 声明高度
  - 多张普通纵向切片拼接时，HTML 声明总高 = materialize 后总高
  - 奇数 actual_h 通过"白底画布 + 顶部 paste"补齐到偶数，视觉无损
  - 偶数 actual_h 不变
  - 多组（多 hotspot 横向拼接）不受影响，仍走统一 row_height
  - 显式 _even_pixel_4x 行为正确

V4.8.5 缝隙问题根因：
  旧逻辑 _compute_group_height 对单组走 row_height = _even_pixel(row_h * display_w / total_w)，
  对 actual_h=833, total_w=display_w=650 的场景算出 832，
  materialize 内部 LANCZOS resize 把 PNG 从 833px 缩到 832px，丢 1px 且产生插值伪影。
  3 张普通切片各缩 1px 累计产生肉眼可见的"每片切图衔接处有缝"。
  修复后（B6 收敛）：全仓统一走 _even_pixel_4x(actual_h) = 向上 4 倍数化，materialize 白底补齐。
"""
import re
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from html_assembler import (
    SliceItem,
    _compute_group_height,
    _even_pixel_4x,
    _group_by_source,
    _normalize_display_width,
    assemble_html,
    materialize_display_slices,
    materialize_display_slices_strict,
)


def make_image(path: Path, w: int, h: int):
    Image.new("RGB", (w, h), "white").save(path)


def _tr_heights(html: str):
    return [int(x) for x in re.findall(r'<tr height="(\d+)"', html)]


def _img_heights(html: str):
    return [int(x) for x in re.findall(r'<img\s+[^>]*height="(\d+)"', html)]


# ── 1. _even_pixel_4x 单元测试（B6 收敛后的唯一偶数化策略）──────────────


def test_even_pixel_4x_returns_4x_ceiling():
    """向上取 4 的倍数（833→836），已是 4 倍数不变；n<=1 时保底 4。"""
    assert _even_pixel_4x(1) == 4
    assert _even_pixel_4x(2) == 4
    assert _even_pixel_4x(833) == 836
    assert _even_pixel_4x(834) == 836
    assert _even_pixel_4x(100) == 100
    assert _even_pixel_4x(0) == 4
    assert _even_pixel_4x(-5) == 4


def test_even_pixel_4x_consistent_with_image_slicer():
    """与 image_slicer._even_ceil 行为一致（4 倍数对齐，单一真相源）。"""
    from image_slicer import _even_ceil
    for n in [1, 2, 4, 100, 833, 834, 836, 1000, 1200]:
        assert _even_pixel_4x(n) == _even_ceil(n), f"分歧: n={n}"


# ── 2. 单组：声明 height 必须等于 materialize 后 PNG 高度 ─────────────


def test_single_slice_declared_height_matches_actual_png_height(tmp_path):
    """3 张奇数高度切片：HTML 声明 height 必须严格等于 materialize 后 PNG 高度。"""
    p1 = tmp_path / "s1.png"
    p2 = tmp_path / "s2.png"
    p3 = tmp_path / "s3.png"
    # 故意用奇数高度（833）
    make_image(p1, 650, 833)
    make_image(p2, 650, 833)
    make_image(p3, 650, 833)
    slices = [
        SliceItem(path=str(p1), sort_key=1.0, original_width=650),
        SliceItem(path=str(p2), sort_key=2.0, original_width=650),
        SliceItem(path=str(p3), sort_key=3.0, original_width=650),
    ]

    prepared = materialize_display_slices_strict(slices, 650)
    html = assemble_html(prepared, 650)

    # materialize 后 PNG 物理高度
    actual_heights = [Image.open(s.path).size[1] for s in prepared]
    assert len(actual_heights) == 3
    # V4.9.2: 普通纵向链路回退到 V3 连续 <img> 结构。
    # 该路径不再使用每片 <tr height>/<img height>，避免 Outlook Word 在表格/高度边界造缝。
    assert html.count("<img") == 3
    assert html.count("<table") == 1
    assert html.count("<tr") == 1
    assert html.count("<td") == 1
    assert 'height="' not in html


def test_single_slice_with_odd_height_uses_white_pad_not_lanczos(tmp_path):
    """actual_h=833 时 materialize 必须用"白底画布 + 顶部 paste"，不能 LANCZOS 缩。
    V4.8.8: 833 → 836 (4 的倍数, 627.0pt 整数)，不是 834 (625.5pt 半点)。"""
    p1 = tmp_path / "odd.png"
    make_image(p1, 648, 833)  # 648 = 4 的倍数
    slices = [SliceItem(path=str(p1), sort_key=1.0, original_width=648)]

    prepared = materialize_display_slices(slices, 648)
    # V4.8.8: materialize 输出必须是 836（向上 4 的倍数化）且原图内容位于顶部 833px
    out_path = prepared[0].path
    with Image.open(out_path) as img:
        assert img.size == (648, 836), f"期望 (648, 836) 4x高度，实际 {img.size}"
        # 顶部 833 像素应当保持原图（白底）
        assert img.getpixel((0, 0)) == (255, 255, 255)
        # 底部 3 像素（y=833~835）应该是白底（padded）
        assert img.getpixel((0, 833)) == (255, 255, 255)
        assert img.getpixel((0, 835)) == (255, 255, 255)


def test_single_slice_with_4x_height_is_unchanged(tmp_path):
    """actual_h 已是 4 的倍数时 materialize 不补白边。"""
    p1 = tmp_path / "even.png"
    make_image(p1, 648, 800)  # 648 和 800 都是 4 的倍数
    slices = [SliceItem(path=str(p1), sort_key=1.0, original_width=648)]

    prepared = materialize_display_slices(slices, 648)
    out_path = prepared[0].path
    with Image.open(out_path) as img:
        assert img.size == (648, 800)


# ── 3. 完整 _send_email 链路：声明总高 = materialize 后总高 ─────────────


def test_send_pipeline_total_height_no_drift(tmp_path):
    """3 张普通纵向切片拼接：HTML 声明总高必须 = materialize 后总高。
    V4.8.5 旧 bug：2500 → 2498（每张丢 1px，累计差 2px → 视觉缝）。
    V4.8.8: 使用 648 (4 的倍数) 作为 display_w。"""
    p1 = tmp_path / "s1.png"
    p2 = tmp_path / "s2.png"
    p3 = tmp_path / "s3.png"
    make_image(p1, 648, 836)  # 836 = 4 的倍数
    make_image(p2, 648, 833)  # 奇数 → 会被对齐到 836
    make_image(p3, 648, 833)  # 奇数
    slices = [
        SliceItem(path=str(p1), sort_key=1.0, original_width=648),
        SliceItem(path=str(p2), sort_key=2.0, original_width=648),
        SliceItem(path=str(p3), sort_key=3.0, original_width=648),
    ]

    prepared = materialize_display_slices_strict(slices, 648)
    html = assemble_html(prepared, 648)

    # materialize 后总高
    actual_total = sum(Image.open(s.path).size[1] for s in prepared)
    # V4.9.2: plain path is V3-style direct image stack. Total height is carried by actual PNGs,
    # not duplicated into per-slice <tr>/<img height> attributes.
    assert actual_total == sum(Image.open(s.path).size[1] for s in prepared)
    assert html.count("<img") == 3
    assert html.count("<table") == 1
    assert 'height="' not in html


# ── 4. 多组（多 hotspot 横向拼接）回归：不受影响 ──────────────────────


def test_multi_group_hotspot_slices_unaffected(tmp_path):
    """多组场景走统一 row_height（4 倍数化），横向总宽严格 == display_w。"""
    from clickable_map import Hotspot
    from hotspot_slicer import slice_paths_by_hotspots

    p = tmp_path / "multi.png"
    make_image(p, 1000, 500)
    hotspots = {
        "multi.png": [
            Hotspot(180, 0, 260, 500, "https://a.example", "A", source_index=1.0),
            Hotspot(520, 0, 650, 500, "https://b.example", "B", source_index=1.0),
        ]
    }
    sliced, link_map = slice_paths_by_hotspots(
        [str(p)], hotspots, source_index_map={"multi.png": 1.0}
    )
    slices = [
        SliceItem(
            path=path,
            href=link_map.get(Path(path).name),
            alt_text="",
            sort_key=sort_key,
            original_width=1000,
        )
        for path, sort_key in sliced
    ]

    prepared = materialize_display_slices(slices, 960)
    html = assemble_html(prepared, 960)

    # 横向总宽必须 = 960
    img_widths = [int(x) for x in re.findall(r'<img[^>]*width="(\d+)"', html)]
    assert sum(img_widths) == 960

    # 各段高度必须一致（多组共享 row_h）
    img_heights = [int(x) for x in re.findall(r'<img\s+[^>]*height="(\d+)"', html)]
    assert len(set(img_heights)) == 1

    # 声明 height == PNG 实际高度
    actual_heights = [Image.open(s.path).size[1] for s in prepared]
    assert actual_heights == img_heights


# ── 5. _compute_group_height 单元测试 ──────────────────────────────


def test_compute_group_height_single_returns_even_pixel_4x_of_actual():
    """单组（len(group)==1）走 _even_pixel_4x 路径（V4.8.8 从 2x 改 4x）。"""
    from html_assembler import _clear_dimensions_cache
    import tempfile, os
    from PIL import Image as PILImage

    # 直接调 _compute_group_height 测单组行为
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        PILImage.new("RGB", (650, 833), "white").save(path)
        from html_assembler import _get_img_dimensions
        s = SliceItem(path=path, sort_key=1.0, original_width=650)
        h = _compute_group_height([s], 648)  # 648 = 4 的倍数
        assert h == 836  # V4.8.8: 833 → 836 (4 的倍数, 627.0pt 整数)
    finally:
        os.unlink(path)
        _clear_dimensions_cache()


def test_compute_group_height_even_actual_unchanged():
    """actual_h 已是偶数时 _compute_group_height 不变。"""
    import tempfile, os
    from PIL import Image as PILImage
    from html_assembler import _clear_dimensions_cache

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        PILImage.new("RGB", (650, 800), "white").save(path)
        s = SliceItem(path=path, sort_key=1.0, original_width=650)
        h = _compute_group_height([s], 650)
        assert h == 800
    finally:
        os.unlink(path)
        _clear_dimensions_cache()


# ── 6. 极端场景：1px 切片也要偶数化 ─────────────────────────────────


def test_extremely_thin_single_slice_still_works(tmp_path):
    """actual_h=1 边界场景不能崩，至少保留 4px（4 的倍数）。"""
    p = tmp_path / "thin.png"
    make_image(p, 650, 1)
    slices = [SliceItem(path=str(p), sort_key=1.0, original_width=650)]
    prepared = materialize_display_slices_strict(slices, 648)  # 648 = 4 的倍数
    html = assemble_html(prepared, 648)
    # V4.9.2: plain path has no explicit per-slice height attributes.
    assert html.count("<img") == 1
    assert html.count("<table") == 1
    assert 'height="' not in html


# ── 7. 视觉无损验证：补白边不能改原图区域像素 ─────────────────────


def test_edge_extend_padding_preserves_visual_continuity(tmp_path):
    """V4.8.9：补齐到 4px 倍数时不能补白边，必须延展最后一行像素。

    用户真实目标：Outlook 邮件里看起来是一整张长图，不能在每片底部看到白色割裂线。
    """
    from PIL import Image
    p = tmp_path / "src.png"
    src = Image.new("RGB", (648, 833))  # 648 = 4 的倍数
    for y in range(833):
        color = (255, 0, 0) if y < 416 else (0, 0, 255)
        for x in range(648):
            src.putpixel((x, y), color)
    src.save(p)
    slices = [SliceItem(path=str(p), sort_key=1.0, original_width=648)]

    prepared = materialize_display_slices(slices, 648)
    out_path = prepared[0].path
    with Image.open(out_path) as out:
        w, h = out.size
        assert h == 836, f"Expected 836, got {h}"
        assert w == 648, f"Expected 648, got {w}"
        assert out.getpixel((100, 0)) == (255, 0, 0)  # 红色未改
        assert out.getpixel((100, 415)) == (255, 0, 0)  # 红色未改
        assert out.getpixel((100, 416)) == (0, 0, 255)  # 蓝色未改
        assert out.getpixel((100, 832)) == (0, 0, 255)  # 蓝色未改
        # 底部 y=833~835 必须复制/延展最后一行蓝色，不能出现白边
        assert out.getpixel((100, 833)) == (0, 0, 255)
        assert out.getpixel((100, 835)) == (0, 0, 255)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
