"""V4.6.9 Bug 3 修复测试：物理切割后多段拼接 = 完整原图按 display_w 缩放

Bug 描述：
  原代码 _build_image_row 不管原图宽度，**每张切割切片都按 display_w 渲染**。
  当原图被物理切割成 N 段（如 1 张原图标 1 个 hotspot → 3 段），
  邮件里 N 段都以 display_w 宽显示，**总宽度 = N × display_w**，
  远超原图缩放宽度 → **图被拉伸错乱**（"碎片错乱"）。

修复：
  给 SliceItem 加 original_width 字段，记录该切片所属原图的总宽度。
  _build_image_row 计算 seg_display_w = display_w * (actual_w / original_width)，
  多段拼接总宽 = display_w（与原图缩放一致）。
"""
import os
import sys
import tempfile
import re

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PIL import Image
from clickable_map import Hotspot
from hotspot_slicer import slice_paths_by_hotspots
from html_assembler import SliceItem, generate_plain_html, assemble_html


def make_image(path, w, h):
    Image.new('RGB', (w, h), 'white').save(path)


class TestV469Bug3MultiStripeWidth:
    """V4.6.9 修复：多段拼接总宽 = display_w"""

    def test_single_hotspot_3_stripes_total_650(self):
        """1000x500 原图 + 1 hotspot(400~600) → 切 3 段(400/200/400) → 段宽 260/130/260 → 总 650"""
        tmp = tempfile.mkdtemp(prefix='v469b3_')
        p = os.path.join(tmp, 'long.png')
        make_image(p, 1000, 500)

        sim = {'long.png': [Hotspot(400, 100, 600, 400, 'https://test.com', 'Btn', source_index=1.0)]}
        sk, lm = slice_paths_by_hotspots([p], sim, source_index_map={'long.png': 1.0})
        slices = [SliceItem(path=path, href=lm.get(os.path.basename(path)),
                            sort_key=k, original_width=1000) for path, k in sk]

        html = generate_plain_html(slices, 650)
        widths = [int(w) for w in re.findall(r'<img[^>]*width="(\d+)"', html)]
        assert sum(widths) == 650, f'总宽应=650, 实际={sum(widths)}, 段={widths}'
        assert widths == [260, 130, 260], f'段宽应=[260,130,260], 实际={widths}'

    def test_no_hotspot_single_slice_total_650(self):
        """1000x500 原图无 hotspot → 1 段 → 段宽 650 → 总 650"""
        tmp = tempfile.mkdtemp(prefix='v469b3_')
        p = os.path.join(tmp, 'long.png')
        make_image(p, 1000, 500)

        sim = {'long.png': []}
        sk, lm = slice_paths_by_hotspots([p], sim, source_index_map={'long.png': 1.0})
        slices = [SliceItem(path=path, href=lm.get(os.path.basename(path)),
                            sort_key=k, original_width=1000) for path, k in sk]

        html = generate_plain_html(slices, 650)
        widths = [int(w) for w in re.findall(r'<img[^>]*width="(\d+)"', html)]
        assert sum(widths) == 650, f'总宽应=650, 实际={sum(widths)}'

    def test_no_original_width_still_keeps_group_width(self):
        """未传 original_width 时，横向分组仍按实际图片宽度保证总宽 = display_w"""
        tmp = tempfile.mkdtemp(prefix='v469b3_')
        p = os.path.join(tmp, 'long.png')
        make_image(p, 1000, 500)

        sim = {'long.png': [Hotspot(400, 100, 600, 400, 'https://test.com', 'Btn', source_index=1.0)]}
        sk, lm = slice_paths_by_hotspots([p], sim, source_index_map={'long.png': 1.0})
        # 不传 original_width：HTML 组装层仍可从实际切片像素宽度分配
        slices = [SliceItem(path=path, href=lm.get(os.path.basename(path)),
                            sort_key=k) for path, k in sk]

        html = generate_plain_html(slices, 650)
        widths = [int(w) for w in re.findall(r'<img[^>]*width="(\d+)"', html)]
        assert sum(widths) == 650, f'未传 original_width 也应总宽=650, 实际={sum(widths)}, 段={widths}'

    def test_multiple_hotspots_proportional(self):
        """1000x500 + 2 hotspot → 5 段 → 段宽按比例 → 总 650"""
        tmp = tempfile.mkdtemp(prefix='v469b3_')
        p = os.path.join(tmp, 'long.png')
        make_image(p, 1000, 500)

        sim = {'long.png': [
            Hotspot(100, 0, 200, 500, 'https://a.com', 'A', source_index=1.0),
            Hotspot(600, 0, 800, 500, 'https://b.com', 'B', source_index=1.0),
        ]}
        sk, lm = slice_paths_by_hotspots([p], sim, source_index_map={'long.png': 1.0})
        # 切割线: [0, 100, 200, 600, 800, 1000] → 5 段宽 [100, 100, 400, 200, 200]
        slices = [SliceItem(path=path, href=lm.get(os.path.basename(path)),
                            sort_key=k, original_width=1000) for path, k in sk]

        html = generate_plain_html(slices, 650)
        widths = [int(w) for w in re.findall(r'<img[^>]*width="(\d+)"', html)]
        # 比例: 100/1000*650=65, 100/1000*650=65, 400/1000*650=260, 200/1000*650=130, 200/1000*650=130
        assert sum(widths) == 650, f'总宽应=650, 实际={sum(widths)}, 段={widths}'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
