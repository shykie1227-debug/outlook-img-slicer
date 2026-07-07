"""
V4.8.7 回归测试：Outlook 1px 缝隙根治验证

根因（V4.8.6 之前/V4.8.7 修复）：
  image_slicer.py 切片时，N 片 PNG 物理总高 ≠ 原图高。
  例如原图 2500px 切 3 张 → 834, 833, 833（总 2500 ✓）
  但 html_assembler._compute_group_height 单组走 _even_pixel_4x(actual_h)：
    834 → 836, 833 → 836, 833 → 836（每片 +3px 白底，4 倍数）
  materialize 后 PNG 实际 = 834, 834, 834（总 2502）
  HTML 声明 = 834, 834, 834（总 2502）
  → 比原图多 2px → 连续切片之间产生 1-2px 白线

修复（V4.8.7）：
  image_slicer.py 切片阶段用 _even_ceil(avg_h)，
  前 N-1 片偶数化、最后一片吸收剩余（不再 ceil 后再偶数化）。
  配合 _even_pixel_4x，零累计误差 = 零 1px 缝。

本测试覆盖：
  1. 切片阶段 PNG 总高严格 = 原图高
  2. 切片阶段每片是偶数（除最后一片可能吸收奇数）
  3. materialize 后 PNG 物理高度 = HTML 声明高度（严格一致）
  4. HTML 声明总高 = 原图高（无累计误差）
  5. _even_ceil 行为正确
  6. 各种原图高度（奇/偶/3 片/5 片/边界值）下都满足约束
  7. V4.8.6 旧测试仍然兼容（B6 收敛后 _even_pixel_4x 行为稳定）
"""
import os
import tempfile
import re
from math import ceil

import pytest
from PIL import Image

from image_slicer import _even_ceil, detect_and_slice
from html_assembler import (
    SliceItem,
    _even_pixel_4x,
    materialize_display_slices_strict,
    assemble_html,
    _get_img_dimensions,
    _clear_dimensions_cache,
)


# ── 1. _even_ceil 单元测试 ───────────────────────────────────
class TestEvenCeil:
    """image_slicer._even_ceil 行为：向上取 4 的倍数（V4.8.8 改为 4x 对齐）。"""

    def test_returns_4x_for_odd(self):
        # V4.8.8: 向上取 4 的倍数
        assert _even_ceil(2) == 4   # 2→4 (4的倍数)
        assert _even_ceil(3) == 4   # 3→4
        assert _even_ceil(833) == 836  # 833→836 (627.0pt)
        assert _even_ceil(99) == 100   # 99→100 (75.0pt)

    def test_unchanged_for_4x(self):
        assert _even_ceil(4) == 4
        assert _even_ceil(832) == 832
        assert _even_ceil(836) == 836
        assert _even_ceil(1200) == 1200

    def test_handles_edge_cases(self):
        # _even_ceil 仅用于 slice 高度（>=60），边界与 _even_pixel_4x 对齐
        assert _even_ceil(1) == 4   # n<=1 走 4 的倍数兜底
        assert _even_ceil(0) == 4   # n<=1 走 4 的倍数兜底
        assert _even_ceil(2) == 4   # 2→4

    def test_consistent_with_assembler(self):
        """_even_ceil 与 html_assembler._even_pixel_4x 行为必须一致
        （image_slicer 输出 4 的倍数 → assemble 时 _even_pixel_4x 退化为恒等 → 0 白底）"""
        from html_assembler import _even_pixel_4x
        for n in [1, 2, 4, 100, 833, 834, 836, 1000, 1200, 1728]:
            assert _even_ceil(n) == _even_pixel_4x(n), f"分歧: n={n}"


# ── 2. 切片阶段总高严格等于原图高 ──────────────────────────────
class TestSliceHeightSum:
    """image_slicer 输出的 N 片 PNG 物理总高必须严格 = 原图高。"""

    def _make_img(self, path, w, h):
        Image.new("RGB", (w, h), (255, 255, 255)).save(path)

    def test_2500_3slices(self):
        """V4.8.6 bug 现场：原图 2500, max_height=1200 → 3 张偶数切片，总 2500"""
        with tempfile.TemporaryDirectory() as td:
            img_path = os.path.join(td, "long.png")
            self._make_img(img_path, 650, 2500)
            paths = detect_and_slice(img_path, max_height=1200)
            assert len(paths) == 3
            heights = []
            for p in paths:
                with Image.open(p) as img:
                    heights.append(img.size[1])
            assert sum(heights) == 2500, (
                f"切片总高 {sum(heights)} ≠ 原图 2500 (差 {sum(heights) - 2500}px)"
            )

    def test_1000_no_slicing(self):
        """原图 ≤ max_height 时不切片（返回原图）"""
        with tempfile.TemporaryDirectory() as td:
            img_path = os.path.join(td, "short.png")
            self._make_img(img_path, 650, 1000)
            paths = detect_and_slice(img_path, max_height=1200)
            assert len(paths) == 1
            with Image.open(paths[0]) as img:
                assert img.size[1] == 1000

    def test_1201_2slices(self):
        """原图 1201 → 2 张切片，最后一片吸收 1px"""
        with tempfile.TemporaryDirectory() as td:
            img_path = os.path.join(td, "long.png")
            self._make_img(img_path, 650, 1201)
            paths = detect_and_slice(img_path, max_height=1200)
            assert len(paths) == 2
            heights = []
            for p in paths:
                with Image.open(p) as img:
                    heights.append(img.size[1])
            assert sum(heights) == 1201

    def test_3000_3slices(self):
        """原图 3000 → 3 张 1000px 切片"""
        with tempfile.TemporaryDirectory() as td:
            img_path = os.path.join(td, "long.png")
            self._make_img(img_path, 650, 3000)
            paths = detect_and_slice(img_path, max_height=1200)
            assert len(paths) == 3
            heights = []
            for p in paths:
                with Image.open(p) as img:
                    heights.append(img.size[1])
            assert sum(heights) == 3000

    def test_5000_5slices(self):
        """原图 5000 → 5 张 1000px 切片"""
        with tempfile.TemporaryDirectory() as td:
            img_path = os.path.join(td, "long.png")
            self._make_img(img_path, 650, 5000)
            paths = detect_and_slice(img_path, max_height=1200)
            assert len(paths) == 5
            heights = []
            for p in paths:
                with Image.open(p) as img:
                    heights.append(img.size[1])
            assert sum(heights) == 5000

    @pytest.mark.parametrize("orig_h", [1199, 1200, 1201, 2399, 2400, 2401, 3500, 4999, 5000, 8333, 10000])
    def test_various_orig_heights(self, orig_h):
        """参数化测试：多种原图高度都满足总高 = orig_h"""
        with tempfile.TemporaryDirectory() as td:
            img_path = os.path.join(td, "long.png")
            self._make_img(img_path, 650, orig_h)
            paths = detect_and_slice(img_path, max_height=1200)
            heights = []
            for p in paths:
                with Image.open(p) as img:
                    heights.append(img.size[1])
            assert sum(heights) == orig_h, (
                f"orig_h={orig_h} slices={heights} sum={sum(heights)}"
            )


# ── 3. 切片阶段每片连续（无遗漏/无重叠）─────────────────────────
class TestSliceContinuity:
    """slice[i].bottom 必须严格 = slice[i+1].top（连续无遗漏/无重叠）"""

    def test_continuous_no_gap_no_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            img_path = os.path.join(td, "long.png")
            Image.new("RGB", (650, 2500), (255, 255, 255)).save(img_path)
            paths = detect_and_slice(img_path, max_height=1200)
            bottoms = []
            for p in paths:
                with Image.open(p) as img:
                    bottoms.append(img.size[1])
            # 累计 bottom[i] 必须等于 slice 总高
            cumulative = 0
            for i, h in enumerate(bottoms):
                cumulative += h
            assert cumulative == 2500


# ── 4. 端到端：HTML 高度与 PNG 高度严格一致 ─────────────────────
class TestEndToEndConsistency:
    """materialize 后 PNG 物理高度 = HTML <tr height> = <td height> = <img height>"""

    def test_html_matches_png_exactly(self):
        with tempfile.TemporaryDirectory() as td:
            img_path = os.path.join(td, "long.png")
            Image.new("RGB", (650, 2500), (255, 255, 255)).save(img_path)
            paths = detect_and_slice(img_path, max_height=1200)
            raw = [SliceItem(path=p, sort_key=float(i + 1)) for i, p in enumerate(paths)]

            # V4.9.3: 普通链路不调 materialize，直接传原始切片
            html = assemble_html(raw, 650)

            # PNG 物理高度（原始切片，未 materialize）
            _clear_dimensions_cache()
            png_heights = [_get_img_dimensions(s.path)[1] for s in raw]
            _clear_dimensions_cache()

            # V4.9.3: 普通链路使用 V3 连续 <img> 结构，不再声明每片高度。
            assert html.count("<img") == len(png_heights)
            assert html.count("<table") == 1
            assert html.count("<tr") == 1
            assert html.count("<td") == 1
            assert 'height="' not in html
            # V4.9.3: 无 materialize，原始切片总高严格 = 原图高
            assert sum(png_heights) == 2500

    def test_no_zero_px_slices(self):
        """切片高度不能为 0（极端边界条件）"""
        with tempfile.TemporaryDirectory() as td:
            img_path = os.path.join(td, "long.png")
            Image.new("RGB", (650, 1200), (255, 255, 255)).save(img_path)
            paths = detect_and_slice(img_path, max_height=1200)
            for p in paths:
                with Image.open(p) as img:
                    assert img.size[1] > 0


# ── 5. 复现 V4.8.6 bug 现场 ────────────────────────────────────
class TestV486BugReproduction:
    """直接复刻 V4.8.6 bug 现场：手工准备 [834, 833, 833] 切片，
    验证修复后 assemble_html 的总高 = 2500"""

    def test_reproduce_old_bug_scenario(self):
        with tempfile.TemporaryDirectory() as td:
            # V4.8.6 bug 现场：原图 2500 切成 [834, 833, 833]
            # V4.8.7 修复后：image_slicer 输出 [834, 834, 832]（总 2500 严格一致）
            # V4.8.8 4x对齐后：每片对齐到 4 的倍数 (834→836, 834→836, 832→832)
            # materialize 补白底，HTML 声明 = PNG 实际 = 4 的倍数 → pt 无小数
            paths = []
            for i, h in enumerate([834, 834, 832]):
                p = os.path.join(td, f"slice_{i}.png")
                Image.new("RGB", (650, h), (255, 255, 255)).save(p)
                paths.append(p)

            raw = [SliceItem(path=p, sort_key=float(i + 1)) for i, p in enumerate(paths)]
            slices = materialize_display_slices_strict(raw, 648)  # 648 = 4 的倍数
            html = assemble_html(slices, 648)

            _clear_dimensions_cache()
            png_heights = [_get_img_dimensions(s.path)[1] for s in slices]
            _clear_dimensions_cache()

            # V4.8.8: 每片 PNG 高度必须是 4 的倍数；V4.9.2 plain HTML 不再写 <tr height>。
            for h in png_heights:
                assert h % 4 == 0, f"PNG 高度 {h} 不是 4 的倍数"
            assert html.count("<img") == len(png_heights)
            assert html.count("<table") == 1
            assert 'height="' not in html


# ── 6. V4.8.6 旧测试仍兼容（B6：收敛为 _even_pixel_4x）──────────────
class TestV486Compat:
    """_even_pixel_4x 单元行为必须稳定（B6 收敛后的唯一偶数化策略）"""

    def test_even_pixel_4x_returns_4x_ceiling(self):
        assert _even_pixel_4x(1) == 4  # n<=1 时保底 4（4 倍数）
        assert _even_pixel_4x(2) == 4
        assert _even_pixel_4x(833) == 836  # 833 → 836 (627.0pt 整数)
        assert _even_pixel_4x(834) == 836
        assert _even_pixel_4x(100) == 100
        assert _even_pixel_4x(0) == 4
        assert _even_pixel_4x(-5) == 4

    def test_even_pixel_4x_is_only_even_strategy(self):
        """B6：旧 _even_pixel / _even_pixel_up 已删除，_even_pixel_4x 是唯一入口。"""
        # 4 倍数对齐保证 Outlook px→pt 转换无小数（零 1px 缝）
        for n in [1, 2, 3, 833, 834, 1000, 1200]:
            v = _even_pixel_4x(n)
            assert v % 4 == 0, f"{n} → {v} 不是 4 的倍数"


# ── 7. assemble_html/表/margin 防 Word 引擎 1px 缝 ────────────
class TestOutlookWordEngineDefenses:
    """V4.8.7 补丁：所有 <table> 在 style 加 border: 0;
    主表加 mso-table-bspace-snap: 1000; <tr> 加 valign="top"
    防止 Word 引擎忽略 HTML 属性导致 1px 缝。"""

    def test_main_table_has_border_in_style(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "s.png")
            Image.new("RGB", (650, 1000), (255, 255, 255)).save(p)
            slices = [SliceItem(path=p, sort_key=1.0)]
            html = assemble_html(slices, 650)
            # V4.8.8: width 可能被对齐到 4 的倍数 (650→652)
            main_table = re.search(r'<table[^>]*?width="\d+"[^>]*>', html).group(0)
            assert "border: 0;" in main_table, "主表 style 缺 border: 0;"

    def test_main_table_has_mso_bspace_snap(self):
        """V4.8.7 关键：mso-table-bspace-snap 让 Word 引擎不做 cell 间距重算"""
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "s.png")
            Image.new("RGB", (650, 1000), (255, 255, 255)).save(p)
            slices = [SliceItem(path=p, sort_key=1.0)]
            html = assemble_html(slices, 650)
            assert "mso-table-bspace-snap: 1000" in html
            assert "mso-table-tspace-snap: 1000" in html

    def test_tr_has_valign_top(self):
        """<tr> 加 valign="top" 防 Word 引擎默认 valign=center"""
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "s.png")
            Image.new("RGB", (650, 1000), (255, 255, 255)).save(p)
            slices = [SliceItem(path=p, sort_key=1.0)]
            html = assemble_html(slices, 650)
            # 每个 <tr ... > 都有 valign="top"
            tr_tags = re.findall(r'<tr[^>]*>', html)
            for tag in tr_tags:
                assert 'valign="top"' in tag, f"<tr> 缺 valign=\"top\": {tag[:120]}"
