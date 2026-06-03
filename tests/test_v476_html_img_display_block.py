"""
V4.7.6 测试 — 邮件缝隙 L8 修复

V4.7.6 新增/增强：
- <img> 加 hspace="0" vspace="0" HTML 属性（Outlook 老版本必需）
- <img> 加 margin: 0; padding: 0 CSS
- 这是 L8 修复（V4.7.5 已修 L1-L7，L8 是最后可能漏的一层）
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_img_tag_has_hspace_vspace_zero(tmp_path):
    """V4.7.6 L8：<img> 必须同时有 hspace="0" vspace="0" HTML 属性"""
    from html_assembler import _build_cell

    # 构造一张测试图
    from PIL import Image
    img_path = tmp_path / "test.png"
    Image.new("RGB", (100, 80), (200, 100, 50)).save(img_path)

    cell_html = _build_cell(
        slice_path=str(img_path),
        cid_or_src="cid:test",
        display_w=650,
        href=None,
        alt="test alt",
        is_base64=False,
    )
    assert 'hspace="0"' in cell_html, f"<img> 缺 hspace=\"0\"：{cell_html[:300]}"
    assert 'vspace="0"' in cell_html, f"<img> 缺 vspace=\"0\"：{cell_html[:300]}"


def test_img_tag_has_margin_padding_zero(tmp_path):
    """V4.7.6 L8 CSS：<img> style 必须包含 margin: 0; padding: 0"""
    from html_assembler import _build_cell

    from PIL import Image
    img_path = tmp_path / "test.png"
    Image.new("RGB", (100, 80), (200, 100, 50)).save(img_path)

    cell_html = _build_cell(
        slice_path=str(img_path),
        cid_or_src="cid:test",
        display_w=650,
        href=None,
        alt="test alt",
        is_base64=False,
    )
    assert "margin: 0" in cell_html, f"<img> 缺 margin: 0 CSS：{cell_html[:300]}"
    assert "padding: 0" in cell_html, f"<img> 缺 padding: 0 CSS：{cell_html[:300]}"


def test_img_tag_display_block_vertical_align_top_still_present(tmp_path):
    """V4.7.6 回归：L1+L2 之前 v4.7.5 修过的必须保持"""
    from html_assembler import _build_cell

    from PIL import Image
    img_path = tmp_path / "test.png"
    Image.new("RGB", (100, 80), (200, 100, 50)).save(img_path)

    cell_html = _build_cell(
        slice_path=str(img_path),
        cid_or_src="cid:test",
        display_w=650,
        href=None,
        alt="test alt",
        is_base64=False,
    )
    # L1: display: block
    assert "display: block" in cell_html, "L1 regression: display:block missing"
    # L2: vertical-align: top
    assert "vertical-align: top" in cell_html, "L2 regression: vertical-align:top missing"
    # L7: border: 0
    assert 'border="0"' in cell_html, "L7 regression: border=0 missing"


def test_a_tag_display_block_for_linked_slices(tmp_path):
    """V4.7.6 回归：<a> 包裹时必须 display:block（链接区域稳定性）"""
    from html_assembler import _build_cell

    from PIL import Image
    img_path = tmp_path / "test.png"
    Image.new("RGB", (100, 80), (200, 100, 50)).save(img_path)

    cell_html = _build_cell(
        slice_path=str(img_path),
        cid_or_src="cid:test",
        display_w=650,
        href="https://example.com",
        alt="linked",
        is_base64=False,
    )
    assert '<a href' in cell_html, "有 href 时必须包 <a>"
    assert "display: block" in cell_html, "<a> 必须 display:block"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
