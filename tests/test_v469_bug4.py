"""V4.6.9 Bug 4 修复测试：HTML 横向拼接（消除'碎片错乱'）

Bug 描述：
  V1 物理切割产物（每段 y1=0, y2=H 的整高竖条）在 HTML 输出时
  每段独占 1 个 <tr> → 纵向堆叠。
  后果：3 段 (400x500 + 200x500 + 400x500) 纵向堆叠 = 3 张图
  视觉上 = 3 段独立图片（不是原图），用户感知'碎片化'。

修复：
  按 sort_key 整数部分（=source_index）分组，同一原图的所有段
  （含 hotspot 派生竖条）拼成 1 个 <tr>，每段独立 <td> 横向并排。
  验证：1 张原图 + 1 hotspot → 1 个 <tr> 含 3 个 <td>。
"""
import os
import sys
import re
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PIL import Image
from clickable_map import Hotspot
from hotspot_slicer import slice_paths_by_hotspots
from html_assembler import SliceItem, generate_plain_html


def make_image(path, w, h):
    Image.new('RGB', (w, h), 'white').save(path)


class TestV469Bug4HorizontalLayout:
    """V4.6.9 修复：HTML 横向拼接（消除碎片化）"""

    def test_one_image_one_hotspot_one_row_three_cells(self):
        """1 张原图 + 1 hotspot（中间）→ 1 个 <tr> 3 个 <td>"""
        tmp = tempfile.mkdtemp(prefix='v469b4_')
        p = os.path.join(tmp, 'long.png')
        make_image(p, 1000, 500)

        sim = {'long.png': [Hotspot(400, 100, 600, 400, 'https://t.com', 'T', source_index=1.0)]}
        sk, lm = slice_paths_by_hotspots([p], sim, source_index_map={'long.png': 1.0})
        slices = [SliceItem(path=path, href=lm.get(os.path.basename(path)),
                            sort_key=k, original_width=1000) for path, k in sk]

        html = generate_plain_html(slices, 650)
        trs = re.findall(r'<tr>.*?</tr>', html, re.S)
        assert len(trs) == 1, f'应 1 个 <tr>，实际 {len(trs)}'
        td_count = len(re.findall(r'<td[^>]*>', trs[0]))
        assert td_count == 3, f'应 3 个 <td>，实际 {td_count}'

    def test_no_hotspot_one_cell(self):
        """1 张原图无 hotspot → 1 个 <tr> 1 个 <td>"""
        tmp = tempfile.mkdtemp(prefix='v469b4_')
        p = os.path.join(tmp, 'long.png')
        make_image(p, 1000, 500)

        sim = {'long.png': []}
        sk, lm = slice_paths_by_hotspots([p], sim, source_index_map={'long.png': 1.0})
        slices = [SliceItem(path=path, href=lm.get(os.path.basename(path)),
                            sort_key=k, original_width=1000) for path, k in sk]

        html = generate_plain_html(slices, 650)
        trs = re.findall(r'<tr>.*?</tr>', html, re.S)
        assert len(trs) == 1
        td_count = len(re.findall(r'<td[^>]*>', trs[0]))
        assert td_count == 1, f'应 1 个 <td>，实际 {td_count}'

    def test_two_hotspots_five_cells_in_one_row(self):
        """1 张原图 + 2 hotspot → 1 个 <tr> 5 个 <td>"""
        tmp = tempfile.mkdtemp(prefix='v469b4_')
        p = os.path.join(tmp, 'long.png')
        make_image(p, 1000, 500)

        sim = {'long.png': [
            Hotspot(200, 0, 300, 500, 'https://a.com', 'A', source_index=1.0),
            Hotspot(700, 0, 800, 500, 'https://b.com', 'B', source_index=1.0),
        ]}
        sk, lm = slice_paths_by_hotspots([p], sim, source_index_map={'long.png': 1.0})
        slices = [SliceItem(path=path, href=lm.get(os.path.basename(path)),
                            sort_key=k, original_width=1000) for path, k in sk]

        html = generate_plain_html(slices, 650)
        trs = re.findall(r'<tr>.*?</tr>', html, re.S)
        assert len(trs) == 1
        td_count = len(re.findall(r'<td[^>]*>', trs[0]))
        assert td_count == 5, f'应 5 个 <td>，实际 {td_count}'

    def test_two_images_two_rows(self):
        """2 张原图（智能切图 Y 切）→ 2 个 <tr>"""
        tmp = tempfile.mkdtemp(prefix='v469b4_')
        paths = []
        for n in ['top.png', 'bot.png']:
            p = os.path.join(tmp, n)
            make_image(p, 1000, 300)
            paths.append(p)

        sim = {
            'top.png': [Hotspot(200, 100, 400, 200, 'https://t.com', 'T', source_index=1.0)],
            'bot.png': [Hotspot(300, 100, 500, 200, 'https://b.com', 'B', source_index=2.0)],
        }
        sk, lm = slice_paths_by_hotspots(paths, sim, source_index_map={'top.png': 1.0, 'bot.png': 2.0})
        slices = [SliceItem(path=path, href=lm.get(os.path.basename(path)),
                            sort_key=k, original_width=1000) for path, k in sk]

        html = generate_plain_html(slices, 650)
        trs = re.findall(r'<tr>.*?</tr>', html, re.S)
        assert len(trs) == 2, f'应 2 个 <tr>（每原图 1 行），实际 {len(trs)}'
        for tr in trs:
            td_count = len(re.findall(r'<td[^>]*>', tr))
            assert td_count == 3, f'每行应 3 个 <td>，实际 {td_count}'

    def test_total_width_equals_display_w(self):
        """每行总宽应 = display_w"""
        tmp = tempfile.mkdtemp(prefix='v469b4_')
        p = os.path.join(tmp, 'long.png')
        make_image(p, 1000, 500)

        sim = {'long.png': [Hotspot(400, 100, 600, 400, 'https://t.com', 'T', source_index=1.0)]}
        sk, lm = slice_paths_by_hotspots([p], sim, source_index_map={'long.png': 1.0})
        slices = [SliceItem(path=path, href=lm.get(os.path.basename(path)),
                            sort_key=k, original_width=1000) for path, k in sk]

        html = generate_plain_html(slices, 650)
        imgs = re.findall(r'<img[^>]*width="(\d+)"', html)
        assert sum(int(w) for w in imgs) == 650, f'总宽应=650, 实际={sum(int(w) for w in imgs)}'

    def test_link_in_correct_cell(self):
        """链接切片应在中间 <td>"""
        tmp = tempfile.mkdtemp(prefix='v469b4_')
        p = os.path.join(tmp, 'long.png')
        make_image(p, 1000, 500)

        sim = {'long.png': [Hotspot(400, 100, 600, 400, 'https://test.com', 'T', source_index=1.0)]}
        sk, lm = slice_paths_by_hotspots([p], sim, source_index_map={'long.png': 1.0})
        slices = [SliceItem(path=path, href=lm.get(os.path.basename(path)),
                            sort_key=k, original_width=1000) for path, k in sk]

        html = generate_plain_html(slices, 650)
        # 找 <a href="https://test.com"> 在第几个 <td>
        # 用正则找包含 https://test.com 的 <td> 块
        tds = re.findall(r'<td[^>]*>.*?</td>', html, re.S)
        link_td_idx = None
        for i, td in enumerate(tds):
            if 'https://test.com' in td:
                link_td_idx = i
                break
        assert link_td_idx == 1, f'链接应在第 2 个 <td>（中间），实际第 {link_td_idx + 1}'
        # 验证左右都是普通图
        assert 'https://test.com' not in tds[0]
        assert 'https://test.com' not in tds[2]

    def test_awkward_widths_sum_exactly_to_display_width(self):
        """非整除宽度也必须严格凑齐 display_w，避免 Outlook 表格换行错位"""
        tmp = tempfile.mkdtemp(prefix='v469b4_')
        p = os.path.join(tmp, 'long.png')
        make_image(p, 1000, 500)

        sim = {'long.png': [
            Hotspot(333, 0, 666, 500, 'https://test.com', 'T', source_index=1.0),
        ]}
        sk, lm = slice_paths_by_hotspots([p], sim, source_index_map={'long.png': 1.0})
        slices = [SliceItem(path=path, href=lm.get(os.path.basename(path)),
                            sort_key=k, original_width=1000) for path, k in sk]

        html = generate_plain_html(slices, 650)
        widths = [int(w) for w in re.findall(r'<img[^>]*width="(\d+)"', html)]
        heights = [int(h) for h in re.findall(r'<img[^>]*height="(\d+)"', html)]
        td_widths = [int(w) for w in re.findall(r'<td[^>]*width="(\d+)"', html)]
        assert sum(widths) == 650, f'img 总宽应=650, 实际={sum(widths)}, 段={widths}'
        assert td_widths == widths, f'td 宽度必须和 img 一致，td={td_widths}, img={widths}'
        assert len(set(heights)) == 1, f'同一行所有分段高度必须一致，实际={heights}'

    def test_href_and_alt_are_html_escaped(self):
        """URL/alt 中的 & 等字符必须转义，否则 Outlook 可能截断 href"""
        tmp = tempfile.mkdtemp(prefix='v469b4_')
        p = os.path.join(tmp, 'long.png')
        make_image(p, 1000, 500)

        sim = {'long.png': [
            Hotspot(400, 100, 600, 400, 'https://example.com/a?x=1&y=2', 'A&B', source_index=1.0),
        ]}
        sk, lm = slice_paths_by_hotspots([p], sim, source_index_map={'long.png': 1.0})
        slices = [SliceItem(path=path, href=lm.get(os.path.basename(path)),
                            alt_text='A&B', sort_key=k, original_width=1000) for path, k in sk]

        html = generate_plain_html(slices, 650)
        assert 'href="https://example.com/a?x=1&amp;y=2"' in html
        assert 'alt="A&amp;B"' in html


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
