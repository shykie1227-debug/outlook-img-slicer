"""
测试 html_assembler 模块
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from html_assembler import assemble_html, get_cid_map


class TestAssembleHtml:
    """测试 assemble_html 函数"""

    def test_gapless_table_generation(self, small_jpg, tall_jpg):
        """测试无缝表格生成"""
        image_paths = [small_jpg, tall_jpg]
        html = assemble_html(image_paths, original_width=800)

        # 验证表格结构（不计 MSO 条件注释里的重复标签）
        assert "<table" in html
        assert "</table>" in html
        # 主内容区有 2 个 <img> 对应 2 张切片
        assert html.count('<img src="cid:slice_') == 2
        assert 'src="cid:slice_001"' in html
        assert 'src="cid:slice_002"' in html

    def test_empty_image_list(self):
        """测试空图片列表"""
        html = assemble_html([], original_width=800)
        assert "<table" in html
        assert "</table>" in html
        # 空图片时 img_tags 为空，不应有任何 cid:slice
        assert "cid:" not in html

    def test_single_image(self, small_jpg):
        """测试单张图片"""
        html = assemble_html([small_jpg], original_width=800)
        assert html.count('<img src="cid:slice_') == 1
        assert 'src="cid:slice_001"' in html

    def test_cid_replacement(self, small_jpg, tall_jpg):
        """测试 CID 方式图片引用"""
        image_paths = [small_jpg, tall_jpg]
        html = assemble_html(image_paths, original_width=800)

        # 验证 CID 格式
        assert 'src="cid:slice_001"' in html
        assert 'src="cid:slice_002"' in html

    def test_multiple_images(self, small_jpg, tall_jpg):
        """测试多张图片 CID"""
        image_paths = [small_jpg, tall_jpg, small_jpg]
        html = assemble_html(image_paths, original_width=800)

        assert 'src="cid:slice_001"' in html
        assert 'src="cid:slice_002"' in html
        assert 'src="cid:slice_003"' in html

    def test_width_in_html(self, small_jpg):
        """测试宽度设置正确写入 HTML"""
        html = assemble_html([small_jpg], original_width=800)
        assert "width: 800px" in html


class TestGetCidMap:
    """测试 get_cid_map 函数"""

    def test_cid_map_generation(self, small_jpg, tall_jpg):
        """测试 CID map 生成"""
        image_paths = [small_jpg, tall_jpg]
        cid_map = get_cid_map(image_paths)
        assert cid_map == {0: "slice_001", 1: "slice_002"}

    def test_empty_list(self):
        """测试空列表"""
        cid_map = get_cid_map([])
        assert cid_map == {}

    def test_single_image(self, small_jpg):
        """测试单张图片"""
        cid_map = get_cid_map([small_jpg])
        assert cid_map == {0: "slice_001"}
