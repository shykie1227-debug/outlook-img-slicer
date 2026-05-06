"""
测试 html_assembler 模块
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from html_assembler import assemble_html, get_html_with_inline_images


class TestAssembleHtml:
    """测试 assemble_html 函数"""

    def test_gapless_table_generation(self, small_jpg, tall_jpg):
        """测试无缝表格生成"""
        image_paths = [small_jpg, tall_jpg]
        html = assemble_html(image_paths, original_width=800)

        # 验证表格结构
        assert "<table" in html
        assert "</table>" in html
        # 每张图片对应一行
        assert html.count("<tr>") == 2
        assert html.count("<td>") == 2

    def test_css_inline_styles(self):
        """测试 CSS 内联样式"""
        html = assemble_html([], original_width=800)
        assert "<style>" in html
        assert ".email-images" in html
        # 验证宽度设置
        assert "width: 800px" in html

    def test_empty_image_list(self):
        """测试空图片列表"""
        html = assemble_html([], original_width=800)
        assert "<table" in html
        assert "</table>" in html
        assert "<tr>" not in html  # 无行

    def test_single_image(self, small_jpg):
        """测试单张图片"""
        html = assemble_html([small_jpg], original_width=800)
        assert html.count("<tr>") == 1
        assert html.count("<td>") == 1


class TestGetHtmlWithInlineImages:
    """测试 get_html_with_inline_images 函数"""

    def test_cid_replacement(self, small_jpg, tall_jpg):
        """测试 CID 方式图片引用"""
        image_paths = [small_jpg, tall_jpg]
        html = get_html_with_inline_images(image_paths, width=800)

        # 验证 CID 格式
        assert 'src="cid:image_0"' in html
        assert 'src="cid:image_1"' in html

    def test_css_inline_styles(self):
        """测试内联 CSS"""
        html = get_html_with_inline_images([], width=800)
        assert "<style>" in html
        assert "width: 800px" in html

    def test_empty_image_list(self):
        """测试空列表"""
        html = get_html_with_inline_images([], width=800)
        assert "<table" in html
        assert "</table>" in html
        assert "<tr>" not in html

    def test_multiple_images(self, small_jpg, tall_jpg):
        """测试多张图片"""
        image_paths = [small_jpg, tall_jpg, small_jpg]
        html = get_html_with_inline_images(image_paths, width=800)

        assert html.count('src="cid:image_') == 3
        assert html.count("<tr>") == 3
