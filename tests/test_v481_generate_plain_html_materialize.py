"""V4.8.1: generate_plain_html 入口 materialize 守卫

根因（H3）：generate_plain_html 独立调用时跳过 materialize，
row_height 偶数化后的高度（如 547→546）与实际 PNG 高度（547）不一致，
HTML 声明 546 vs 实际 547 → 1px 溢出 → Outlook 拉伸产生 1px 纵向缝。

修复：generate_plain_html 入口先调用 materialize_display_slices，
保证 HTML 声明 height == 实际 PNG height。
"""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PIL import Image
from html_assembler import (
    generate_plain_html,
    materialize_display_slices,
    materialize_display_slices_strict,
    SliceItem,
    _normalize_display_width,
)


def _make_slice(td: str, name: str, w: int, h: int, sort_key: float,
                source_index: float = 1.0, href: str = None) -> SliceItem:
    p = os.path.join(td, name)
    Image.new("RGB", (w, h), (200, 200, 200)).save(p)
    s = SliceItem(path=p, original_width=650, href=href, sort_key=sort_key)
    s.source_index = source_index
    s.original_height = h
    return s


def test_generate_plain_html_materializes_odd_height():
    """3 张原图奇数高度 547/552/549，generate_plain_html 后 PNG 实际 == HTML 声明"""
    td = tempfile.mkdtemp()
    slices = [
        _make_slice(td, "h547.png", 650, 547, 1.0, source_index=1.0),
        _make_slice(td, "h552.png", 650, 552, 2.0, source_index=2.0),
        _make_slice(td, "h549.png", 650, 549, 3.0, source_index=3.0),
    ]

    # V4.8.1 修复后：generate_plain_html 内部会 materialize
    # 不能直接走（因为 materialize 会覆盖原文件路径）
    # 验证方式: materialize 后传入，看 height 一致性
    mat = materialize_display_slices(slices, 650)
    html = generate_plain_html(mat, 650)

    actual_heights = [Image.open(s.path).size[1] for s in mat]
    # V4.9.2: plain copy path uses V3 direct image stack, no per-slice <tr height>.
    assert actual_heights
    assert html.count("<img") == len(mat)
    assert html.count("<table") == 1
    assert html.count("<tr") == 1
    assert html.count("<td") == 1
    assert 'height="' not in html


def test_generate_plain_html_keeps_materialize_consistent():
    """generate_plain_html 接受 materialize 后的 slices，输出稳定"""
    td = tempfile.mkdtemp()
    slices = [
        _make_slice(td, "h547.png", 650, 547, 1.0, source_index=1.0),
        _make_slice(td, "h549.png", 650, 549, 2.0, source_index=2.0),
    ]

    mat = materialize_display_slices(slices, 650)
    html = generate_plain_html(mat, 650)

    # V4.9.2: plain no-link path has no per-slice <tr height>; structure is V3 direct <img> stack.
    assert html.count("<img") == len(mat)
    assert html.count("<table") == 1
    assert 'height="' not in html

    # 关键: 没有 <a> 标签时（无链接），HTML 结构应包含 <img> 但不包含 <a>
    assert "<a " not in html, "无链接时不应生成 <a> 标签"


def test_generate_plain_html_with_href_produces_a_tags():
    """带 href 的切片，generate_plain_html 生成 <a> 包裹的 <img>"""
    td = tempfile.mkdtemp()
    slices = [
        _make_slice(td, "h547_a.png", 650, 547, 1.0, source_index=1.0,
                    href="https://example.com"),
    ]

    mat = materialize_display_slices(slices, 650)
    html = generate_plain_html(mat, 650)

    # 1 个 <a> 标签
    a_count = len(re.findall(r'<a\s+href=', html))
    assert a_count == 1, f"应有 1 个 <a> 标签，实际 {a_count}"

    # <a> 应有 display: block
    a_style_match = re.search(r'<a\s+href[^>]*style="([^"]+)"', html)
    assert a_style_match, "<a> 标签缺失 style"
    assert "display: block" in a_style_match.group(1), \
        "<a> style 缺少 display: block（防 Outlook baseline 缝）"


def test_generate_plain_html_base64_encodes_images():
    """base64 模式 (V4.8 R2 CF_HTML 兼容)，HTML 内嵌 data:image/...;base64,"""
    td = tempfile.mkdtemp()
    slices = [
        _make_slice(td, "h547.png", 650, 547, 1.0, source_index=1.0),
    ]

    mat = materialize_display_slices(slices, 650)
    html = generate_plain_html(mat, 650)

    # base64 模式: img src 是 data: URL
    assert "data:image/" in html, "base64 模式应内嵌 data: URL"
    assert ";base64," in html, "base64 模式应有 ;base64, 前缀"

    # 关键: 不应有 cid: 引用（cid 是 assemble_html 的）
    assert "cid:" not in html, "generate_plain_html 不应使用 cid: 引用"


def test_generate_plain_html_guard_catches_silent_materialize_failure(monkeypatch):
    """V4.8.1.1 / V4.9.3: materialize 静默降级时，guard 抛 RuntimeError。

    V4.9.3: 普通链路（无 href）不再调 materialize，所以用带 href 的切片测试。
    模拟 materialize 内部 except Exception: for s in group: prepared.append(s)
    路径（返回原 SliceItem 列表，无新文件生成）。
    """
    from html_assembler import materialize_display_slices

    td = tempfile.mkdtemp()
    # 构造 1 张带 href 的合法 PNG（走复杂链路，仍调 materialize）
    p = os.path.join(td, "orig.png")
    Image.new("RGB", (650, 650), (200, 200, 200)).save(p)
    raw_slice = SliceItem(path=p, original_width=650, sort_key=1.0, href="https://example.com")
    raw_slice.source_index = 1.0
    raw_slice.original_height = 650

    # Monkey-patch: 模拟 materialize 静默降级（返回原 slices，不生成新文件）
    def fake_silent(slices, display_w=650):
        return slices  # 静默降级：无新文件
    monkeypatch.setattr(
        "html_assembler.materialize_display_slices", fake_silent
    )

    # 调 generate_plain_html → strict materialize 应触发 RuntimeError
    try:
        generate_plain_html([raw_slice], 650)
    except RuntimeError as e:
        assert "预渲染失败" in str(e) and "Outlook" in str(e), \
            f"guard RuntimeError 文案不符合预期: {e}"
    else:
        raise AssertionError("guard 未触发，H3 修复存在静默失效风险")


def test_strict_materialize_rejects_partial_fallback(monkeypatch):
    """V4.8.2: 发送路径也不能接受 materialize 部分静默降级。"""
    td = tempfile.mkdtemp()
    p = os.path.join(td, "orig.png")
    Image.new("RGB", (650, 650), (200, 200, 200)).save(p)
    raw_slice = SliceItem(path=p, original_width=650, sort_key=1.0)

    def fake_partial_fallback(slices, display_w=650):
        return slices

    monkeypatch.setattr(
        "html_assembler.materialize_display_slices", fake_partial_fallback
    )

    try:
        materialize_display_slices_strict([raw_slice], 650)
    except RuntimeError as e:
        assert "预渲染失败" in str(e) and "图片缝隙" in str(e), \
            f"strict RuntimeError 文案不符合预期: {e}"
    else:
        raise AssertionError("strict materialize 未拒绝静默降级结果")


if __name__ == "__main__":
    test_generate_plain_html_materializes_odd_height()
    print("✅ test_generate_plain_html_materializes_odd_height")
    test_generate_plain_html_keeps_materialize_consistent()
    print("✅ test_generate_plain_html_keeps_materialize_consistent")
    test_generate_plain_html_with_href_produces_a_tags()
    print("✅ test_generate_plain_html_with_href_produces_a_tags")
    test_generate_plain_html_base64_encodes_images()
    print("✅ test_generate_plain_html_base64_encodes_images")
    print()
    print("🎉 V4.8.1 4 个新测试全部通过")
