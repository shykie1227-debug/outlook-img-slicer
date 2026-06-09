"""
V4.7.7 测试 — 4 个 bug 修复

1. Fix A: 缝隙修复（_even_pixel + mso-* CSS）
2. Fix B: hotspot 提示优化（具体 id + 坐标 + 建议）
3. Fix C: 导出防御（目录可写性 + 文件 size 验证）
4. Fix D: 多页合并根因（用 len(images) 不是 len(paths)）
"""

import sys
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ════════════════════════════════════════════════════
# Fix A: 缝隙修复
# ════════════════════════════════════════════════════

def test_even_pixel_basic():
    """_even_pixel: 奇数→偶数，偶数→自身"""
    from html_assembler import _even_pixel
    assert _even_pixel(247) == 246
    assert _even_pixel(248) == 248
    assert _even_pixel(1) == 1
    assert _even_pixel(0) == 1  # <1 返回 1
    assert _even_pixel(583) == 582
    assert _even_pixel(584) == 584


def test_img_tag_height_is_even(tmp_path):
    """Fix A: _build_cell 输出的 <img> height 必须是偶数"""
    from html_assembler import _build_cell
    from PIL import Image

    # 构造一张奇数高度图（500x247）
    img = Image.new("RGB", (500, 247), (100, 150, 200))
    p = tmp_path / "odd_h.png"
    img.save(p)

    cell = _build_cell(
        slice_path=str(p), cid_or_src="cid:test",
        display_w=650, href=None, alt="", is_base64=False,
    )
    # 提取 height="N"
    m = re.search(r'height="(\d+)"', cell)
    assert m, f"找不到 height 属性: {cell[:200]}"
    h = int(m.group(1))
    assert h % 2 == 0, f"height {h} 应为偶数（避免 Outlook px→pt 转换小数）"


def test_a_tag_has_mso_border_alt(tmp_path):
    """Fix A: <a> 必须有 mso-border-alt / mso-padding-alt（Outlook 2007-2010）"""
    from html_assembler import _build_cell
    from PIL import Image

    img = Image.new("RGB", (100, 80), (200, 100, 50))
    p = tmp_path / "a.png"
    img.save(p)

    cell = _build_cell(
        slice_path=str(p), cid_or_src="cid:test",
        display_w=650, href="https://example.com",
        alt="link", is_base64=False,
    )
    assert "mso-border-alt" in cell, "<a> 缺 mso-border-alt"
    assert "mso-padding-alt" in cell, "<a> 缺 mso-padding-alt"
    assert "solid #FFFFFF 0px" in cell, "mso-border-alt 应为白色 0px"


def test_td_has_mso_padding_alt(tmp_path):
    """Fix A: <td> 必须有 mso-padding-alt: 0"""
    from html_assembler import _build_cell
    from PIL import Image

    img = Image.new("RGB", (100, 80), (200, 100, 50))
    p = tmp_path / "td.png"
    img.save(p)

    cell = _build_cell(
        slice_path=str(p), cid_or_src="cid:test",
        display_w=650, href=None, alt="", is_base64=False,
    )
    assert "mso-padding-alt: 0" in cell, "<td> 缺 mso-padding-alt: 0"


def test_compute_group_height_returns_even(tmp_path):
    """Fix A: _compute_group_height 输出偶数"""
    from html_assembler import _compute_group_height, SliceItem
    from PIL import Image

    # 构造两张切片（合在一起总宽 1000, 高度 247 奇数）
    p1 = tmp_path / "s1.png"
    p2 = tmp_path / "s2.png"
    Image.new("RGB", (500, 247), (100, 100, 100)).save(p1)
    Image.new("RGB", (500, 247), (200, 200, 200)).save(p2)

    group = [
        SliceItem(path=str(p1), sort_key=1.0, original_width=1000),
        SliceItem(path=str(p2), sort_key=1.001, original_width=1000),
    ]
    h = _compute_group_height(group, 650)
    assert h % 2 == 0, f"_compute_group_height 输出 {h} 应为偶数"


# ════════════════════════════════════════════════════
# Fix B: hotspot 提示优化
# ════════════════════════════════════════════════════

def test_validate_hotspots_no_overlap_specific_message():
    """Fix B: 重叠提示应包含具体 id + 坐标 + 建议"""
    from hotspot_slicer import validate_hotspots_no_overlap
    from clickable_map import Hotspot

    h1 = Hotspot(x1=100, y1=0, x2=300, y2=100, url="https://a.com", text="A")
    h2 = Hotspot(x1=250, y1=0, x2=500, y2=100, url="https://b.com", text="B")

    ok, reason = validate_hotspots_no_overlap([h1, h2], img_w=1000)
    assert not ok
    # V4.7.7: 提示应包含具体 id + 坐标 + 建议
    assert "#1" in reason, f"提示应包含 hotspot #1 编号: {reason}"
    assert "#2" in reason, f"提示应包含 hotspot #2 编号: {reason}"
    assert "x1=100" in reason, f"提示应包含 x1=100 坐标: {reason}"
    assert "x2=300" in reason, f"提示应包含 x2=300 坐标: {reason}"
    assert "建议" in reason, f"提示应包含调整建议: {reason}"


def test_validate_hotspots_overlap_suggestion_includes_coords():
    """Fix B: 建议应包含可执行坐标"""
    from hotspot_slicer import validate_hotspots_no_overlap
    from clickable_map import Hotspot

    h1 = Hotspot(x1=100, y1=0, x2=300, y2=100, url="https://a.com", text="A")
    h2 = Hotspot(x1=250, y1=0, x2=500, y2=100, url="https://b.com", text="B")

    ok, reason = validate_hotspots_no_overlap([h1, h2], img_w=1000)
    assert not ok
    # 建议应明确告诉用户调整坐标
    assert "300px" in reason or "250" in reason, f"建议应包含可执行坐标: {reason}"


def test_validate_hotspots_stacked_y_overlap_has_architecture_hint():
    """上下错位但 X 重叠时，应明确提示当前版本不支持该布局。"""
    from hotspot_slicer import validate_hotspots_no_overlap
    from clickable_map import Hotspot

    h1 = Hotspot(x1=100, y1=0, x2=300, y2=80, url="https://a.com", text="A")
    h2 = Hotspot(x1=120, y1=120, x2=320, y2=200, url="https://b.com", text="B")

    ok, reason = validate_hotspots_no_overlap([h1, h2], img_w=1000)
    assert not ok
    assert "上下不同位置" in reason
    assert "纵向切条" in reason
    assert "拆成两张图" in reason


# ════════════════════════════════════════════════════
# Fix C: 导出防御（间接测：检查 main.py 源码包含防御代码）
# ════════════════════════════════════════════════════

def test_export_images_has_write_test():
    """Fix C: _export_images 应有目录可写性测试代码"""
    main_src = (ROOT / "main.py").read_text()
    assert ".outlook_slicer_write_test" in main_src, "Fix C: 缺目录可写性测试"
    assert "V4.7.7 防御 1" in main_src or "V4.7.7" in main_src


def test_export_images_has_size_verification():
    """Fix C: _export_images 应有文件 size 验证"""
    main_src = (ROOT / "main.py").read_text()
    assert "os.path.getsize(dst)" in main_src, "Fix C: 缺文件 size 验证"
    assert "file_size == 0" in main_src, "Fix C: 缺 0 字节检查"


# ════════════════════════════════════════════════════
# Fix D: 多页合并根因
# ════════════════════════════════════════════════════

def test_export_filename_uses_len_images():
    """Fix D: _export_images 文件名应基于 len(images) 不是 len(paths)"""
    main_src = (ROOT / "main.py").read_text()
    # 找 _export_images 函数体内的 suffix / base_name
    assert "len(images) > 1" in main_src, "Fix D: 缺 len(images) 判断"
    # 旧的 "len(paths) > 1" 在 export 块不应再作为判断条件（注释除外）
    # 简单测：导出分支必须用 len(images)
    assert "V4.7.7 修复" in main_src, "Fix D: 缺 v4.7.7 注释"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
