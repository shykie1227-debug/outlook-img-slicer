"""
测试 fixtures
"""
import os
import tempfile
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def temp_dir():
    """创建临时目录，测试后自动清理"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def small_jpg(temp_dir):
    """创建一个小于阈值的 JPG 图片（高度 <= 1500px）"""
    path = os.path.join(temp_dir, "small.jpg")
    img = Image.new("RGB", (800, 1000), color="red")
    img.save(path, "JPEG")
    return path


@pytest.fixture
def tall_jpg(temp_dir):
    """创建一个高大的 JPG 图片（高度 > 1500px）"""
    path = os.path.join(temp_dir, "tall.jpg")
    img = Image.new("RGB", (800, 3000), color="blue")
    img.save(path, "JPEG")
    return path


@pytest.fixture
def tall_png_transparent(temp_dir):
    """创建一个高大的 PNG 图片（带透明通道）"""
    path = os.path.join(temp_dir, "tall_transparent.png")
    img = Image.new("RGBA", (800, 3000), color=(255, 0, 0, 128))
    img.save(path, "PNG")
    return path


@pytest.fixture
def exact_boundary_jpg(temp_dir):
    """创建一个高度恰好 1500px 的 JPG 图片（边界测试）"""
    path = os.path.join(temp_dir, "exact_boundary.jpg")
    img = Image.new("RGB", (800, 1500), color="green")
    img.save(path, "JPEG")
    return path


@pytest.fixture
def very_tall_jpg(temp_dir):
    """创建一个很高的 JPG 图片（4000px，用于多切片测试）"""
    path = os.path.join(temp_dir, "very_tall.jpg")
    img = Image.new("RGB", (800, 4000), color="yellow")
    img.save(path, "JPEG")
    return path


@pytest.fixture
def bmp_image(temp_dir):
    """创建 BMP 格式测试图片"""
    path = os.path.join(temp_dir, "test.bmp")
    img = Image.new("RGB", (600, 2000), color="purple")
    img.save(path, "BMP")
    return path


@pytest.fixture
def webp_image(temp_dir):
    """创建 WebP 格式测试图片"""
    path = os.path.join(temp_dir, "test.webp")
    img = Image.new("RGB", (600, 2000), color="orange")
    img.save(path, "WEBP")
    return path


@pytest.fixture
def gif_image(temp_dir):
    """创建 GIF 格式测试图片"""
    path = os.path.join(temp_dir, "test.gif")
    img = Image.new("RGB", (600, 2000), color="cyan")
    img.save(path, "GIF")
    return path


@pytest.fixture
def invalid_file(temp_dir):
    """创建无效文件（文本文件伪装成图片）"""
    path = os.path.join(temp_dir, "invalid.txt")
    with open(path, "w") as f:
        f.write("This is not an image")
    return path
