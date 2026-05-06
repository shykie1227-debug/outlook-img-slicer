"""
测试 image_slicer 模块
"""
import os
import sys

import pytest
from PIL import Image

# 将项目根目录加入 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from image_slicer import detect_and_slice, get_image_info


class TestDetectAndSlice:
    """测试 detect_and_slice 函数"""

    def test_jpg_slice(self, tall_jpg):
        """测试 JPG 正常切片"""
        result = detect_and_slice(tall_jpg, max_height=1500)
        # 高度 3000 / 1500 = 2 片
        assert len(result) == 2
        assert all(os.path.exists(p) for p in result)

    def test_png_transparency(self, tall_png_transparent):
        """测试 PNG 透明通道保留"""
        result = detect_and_slice(tall_png_transparent, max_height=1500)
        assert len(result) == 2
        # 验证透明通道保留
        with Image.open(result[0]) as img:
            assert img.mode == "RGBA"

    def test_small_image_no_slice(self, small_jpg):
        """测试小于阈值不切片"""
        result = detect_and_slice(small_jpg, max_height=1500)
        assert len(result) == 1
        assert result[0] == small_jpg

    def test_invalid_file(self, invalid_file):
        """测试无效文件"""
        with pytest.raises(Exception):
            detect_and_slice(invalid_file, max_height=1500)

    def test_exact_boundary_no_slice(self, exact_boundary_jpg):
        """测试恰好边界不切片（高度 == 1500）"""
        result = detect_and_slice(exact_boundary_jpg, max_height=1500)
        assert len(result) == 1
        assert result[0] == exact_boundary_jpg

    def test_multi_slice_count(self, very_tall_jpg):
        """测试多切片数量计算（4000px -> 3片）"""
        result = detect_and_slice(very_tall_jpg, max_height=1500)
        # (4000 + 1500 - 1) // 1500 = 3
        assert len(result) == 3

    def test_different_formats(self, bmp_image, webp_image, gif_image):
        """测试不同格式支持"""
        for path in [bmp_image, webp_image, gif_image]:
            result = detect_and_slice(path, max_height=1500)
            assert len(result) == 2  # 2000px / 1500px = 2片


class TestGetImageInfo:
    """测试 get_image_info 函数"""

    def test_get_info_jpg(self, small_jpg):
        """测试获取 JPG 信息"""
        info = get_image_info(small_jpg)
        assert info["width"] == 800
        assert info["height"] == 1000
        assert info["format"] == "JPEG"

    def test_get_info_png(self, tall_png_transparent):
        """测试获取 PNG 信息"""
        info = get_image_info(tall_png_transparent)
        assert info["width"] == 800
        assert info["height"] == 3000
        assert info["format"] == "PNG"

    def test_get_info_invalid(self, invalid_file):
        """测试无效文件信息获取"""
        with pytest.raises(Exception):
            get_image_info(invalid_file)
