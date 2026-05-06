"""
图像切片器模块
将长图按指定高度切片，支持 JPG/PNG/BMP/WebP/GIF
"""

import os
import tempfile
from typing import List
from pathlib import Path
from PIL import Image


def detect_and_slice(image_path: str, max_height: int = 1500) -> List[str]:
    """
    检测图像高度，必要时切片

    Args:
        image_path: 图片文件路径
        max_height: 单片最大高度，默认 1500px

    Returns:
        切片后的临时文件路径列表
    """
    img = Image.open(image_path)
    orig_w, orig_h = img.size

    # 无需切片
    if orig_h <= max_height:
        return [image_path]

    # 计算切片数量
    slice_count = (orig_h + max_height - 1) // max_height
    slice_paths: List[str] = []
    temp_dir = tempfile.gettempdir()

    for i in range(slice_count):
        top = i * max_height
        bottom = min((i + 1) * max_height, orig_h)
        slice_h = bottom - top

        # 裁剪对应区域，保持原始宽度不变
        slice_img = img.crop((0, top, orig_w, bottom))
        slice_img = slice_img.resize((orig_w, slice_h), Image.LANCZOS)

        # 保存切片
        ext = Path(image_path).suffix.lower()
        slice_path = os.path.join(temp_dir, f"slice_{i}{ext}")
        slice_img.save(slice_path, quality=95)
        slice_paths.append(slice_path)

    return slice_paths


def get_image_info(image_path: str) -> dict:
    """获取图片基本信息"""
    img = Image.open(image_path)
    return {
        "width": img.size[0],
        "height": img.size[1],
        "format": img.format,
    }
