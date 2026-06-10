"""
V4.8.6 普通纵向切片无 1px 缝隙回归测试

覆盖 V4.8.6 修复：
  - materialize 输出的 PNG 物理高度 = HTML <tr height> 声明高度
  - materialize 输出的 PNG 物理高度 = HTML <img height> 声明高度
  - 多张普通纵向切片拼接时，HTML 声明总高 = materialize 后总高
  - 奇数 actual_h 通过"白底画布 + 顶部 paste"补齐到偶数，视觉无损
  - 偶数 actual_h 不变
  - 多组（多 hotspot 横向拼接）不受影响，仍走统一 row_height
  - 显式 _even_pixel_up 行为正确

V4.8.5 缝隙问题根因：
  旧逻辑 _compute_group_height 对单组走 row_height = _even_pixel(row_h * display_w / total_w)，
  对 actual_h=833, total_w=display_w=650 的场景算出 832，
  materialize 内部 LANCZOS resize 把 PNG 从 833px 缩到 832px，丢 1px 且产生插值伪影。
  3 张普通切片各缩 1px 累计产生肉眼可见的"每片切图衔接处有缝"。
  修复后：单组走 _even_pixel_up(actual_h) = 向上偶数化，materialize 白底补齐。
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
    _even_pixel,
    _even_pixel_up,
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


# ── 1. _even_pixel_up 单元测试 ──────────────────────────────────────


def test_even_pixel_up_returns_even_ceiling():
    """奇数向上偶数化（833→834），偶数不变；n<=1 时保底 1。"""
    assert _even_pixel_up(1) == 1
    assert _even_pixel_up(2) == 2
    assert _even_pixel_up(833) == 834
    assert _even_pixel_up(834) == 834
    assert _even_pixel_up(100) == 100
    assert _even_pixel_up(0) == 1
    assert _even_pixel_up(-5) == 1


def test_even_pixel_still_rounds_down():
    """V4.7.8 旧行为保留：奇数向下偶数化（833→832）。多组场景仍依赖此函数。"""
    assert _even_pixel(1) == 1
    assert _even_pixel(833) == 832
    assert _even_pixel(834) == 834


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
    # HTML 声明的 tr height
    tr_heights = _tr_heights(html)
    # HTML 声明的 img height
    img_heights = _img_heights(html)

    assert len(actual_heights) == 3
    assert actual_heights == tr_heights, (
        f"V4.8.6 缝隙源：materialize 实际 PNG 高度 {actual_heights} "
        f"与 HTML <tr height> {tr_heights} 不一致"
    )
    assert actual_heights == img_heights, (
        f"V4.8.6 缝隙源：materialize 实际 PNG 高度 {actual_heights} "
        f"与 HTML <img height> {img_heights} 不一致"
    )


def test_single_slice_with_odd_height_uses_white_pad_not_lanczos(tmp_path):
    """actual_h=833 时 materialize 必须用"白底画布 + 顶部 paste"，不能 LANCZOS 缩。"""
    p1 = tmp_path / "odd.png"
    make_image(p1, 650, 833)
    slices = [SliceItem(path=str(p1), sort_key=1.0, original_width=650)]

    prepared = materialize_display_slices(slices, 650)
    # material 输出必须是 834（向上偶数化）且原图内容位于顶部 833px
    out_path = prepared[0].path
    with Image.open(out_path) as img:
        assert img.size == (650, 834), f"期望 (650, 834) 偶数高度，实际 {img.size}"
        # 顶部 833 像素应当保持原图（白底）
        # 像素 (0, 0) 应该是白色（来自原图）
        assert img.getpixel((0, 0)) == (255, 255, 255)
        # 底部 1 像素（y=833）应该是白底（padded）
        assert img.getpixel((0, 833)) == (255, 255, 255)


def test_single_slice_with_even_height_is_unchanged(tmp_path):
    """actual_h 已是偶数时 materialize 不补白边。"""
    p1 = tmp_path / "even.png"
    make_image(p1, 650, 800)
    slices = [SliceItem(path=str(p1), sort_key=1.0, original_width=650)]

    prepared = materialize_display_slices(slices, 650)
    out_path = prepared[0].path
    with Image.open(out_path) as img:
        assert img.size == (650, 800)


# ── 3. 完整 _send_email 链路：声明总高 = materialize 后总高 ─────────────


def test_send_pipeline_total_height_no_drift(tmp_path):
    """3 张普通纵向切片拼接：HTML 声明总高必须 = materialize 后总高。
    V4.8.5 旧 bug：2500 → 2498（每张丢 1px，累计差 2px → 视觉缝）。"""
    p1 = tmp_path / "s1.png"
    p2 = tmp_path / "s2.png"
    p3 = tmp_path / "s3.png"
    make_image(p1, 650, 834)
    make_image(p2, 650, 833)  # 奇数
    make_image(p3, tmp_path and 650, 833) if False else make_image(p3, 650, 833)
    slices = [
        SliceItem(path=str(p1), sort_key=1.0, original_width=650),
        SliceItem(path=str(p2), sort_key=2.0, original_width=650),
        SliceItem(path=str(p3), sort_key=3.0, original_width=650),
    ]

    prepared = materialize_display_slices_strict(slices, 650)
    html = assemble_html(prepared, 650)

    # materialize 后总高（向上偶数化后）
    actual_total = sum(Image.open(s.path).size[1] for s in prepared)
    # HTML 声明总高
    tr_total = sum(_tr_heights(html))
    img_total = sum(_img_heights(html))

    assert actual_total == tr_total == img_total, (
        f"V4.8.6 缝隙源：materialize 实际总高 {actual_total} "
        f"≠ tr 总高 {tr_total} ≠ img 总高 {img_total}"
    )


# ── 4. 多组（多 hotspot 横向拼接）回归：不受影响 ──────────────────────


def test_multi_group_hotspot_slices_unaffected(tmp_path):
    """多组场景仍走原 _even_pixel 逻辑，row_height = 统一高度。"""
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


def test_compute_group_height_single_returns_even_pixel_up_of_actual():
    """单组（len(group)==1）走 _even_pixel_up 路径。"""
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
        h = _compute_group_height([s], 650)
        assert h == 834  # 833 → 834 向上偶数化
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
    """actual_h=1 边界场景不能崩，至少保留 1px。"""
    p = tmp_path / "thin.png"
    make_image(p, 650, 1)
    slices = [SliceItem(path=str(p), sort_key=1.0, original_width=650)]
    prepared = materialize_display_slices_strict(slices, 650)
    html = assemble_html(prepared, 650)
    # _even_pixel_up(1) = max(1, 1) = 1，所以 tr height=1
    assert _tr_heights(html) == [1]


# ── 7. 视觉无损验证：补白边不能改原图区域像素 ─────────────────────


def test_white_pad_preserves_original_pixels(tmp_path):
    """V4.8.6 修复用"顶部 paste + 底部白边"，原图区域像素不能被改。"""
    # 原图：上半部分红色，下半部分蓝色
    from PIL import Image
    p = tmp_path / "src.png"
    src = Image.new("RGB", (650, 833))
    for y in range(833):
        if y < 416:
            for x in range(650):
                src.putpixel((x, y), (255, 0, 0))  # 红色
        else:
            for x in range(650):
                src.putpixel((x, y), (0, 0, 255))  # 蓝色
    src.save(p)
    slices = [SliceItem(path=str(p), sort_key=1.0, original_width=650)]

    prepared = materialize_display_slices(slices, 650)
    out_path = prepared[0].path
    with Image.open(out_path) as out:
        # 原图区 0..832 像素保留
        assert out.size == (650, 834)
        assert out.getpixel((100, 0)) == (255, 0, 0)  # 红色未改
        assert out.getpixel((100, 415)) == (255, 0, 0)  # 红色未改
        assert out.getpixel((100, 416)) == (0, 0, 255)  # 蓝色未改
        assert out.getpixel((100, 832)) == (0, 0, 255)  # 蓝色未改
        # 底部 y=833 是补的白边
        assert out.getpixel((100, 833)) == (255, 255, 255)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
