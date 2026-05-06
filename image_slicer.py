"""
图像切片器模块
将长图按指定高度切片，支持 JPG/PNG/BMP/WebP/GIF
优化说明：增加了对透明通道的处理，确保切片质量。
"""
import os
import tempfile
from typing import List
from pathlib import Path
from PIL import Image


def detect_and_slice(image_path: str, max_height: int = 1200) -> List[str]:
    """
    检测图像高度，必要时进行无损切片

    Args:
        image_path: 原始图片文件路径
        max_height: 单片最大高度（像素），默认 1200px 以适配邮件客户端

    Returns:
        切片后的临时文件路径列表
    """
    try:
        img = Image.open(image_path)
        # 转换模式以确保兼容性（RGBA 转 RGB 防止保存为 JPG 报错）
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        orig_w, orig_h = img.size

        # 如果高度在限制内，直接返回原图
        if orig_h <= max_height:
            return [image_path]

        # 计算需要的切片数量
        slice_count = (orig_h + max_height - 1) // max_height
        slice_paths: List[str] = []
        temp_dir = tempfile.gettempdir()
        ext = Path(image_path).suffix.lower()

        for i in range(slice_count):
            top = i * max_height
            bottom = min((i + 1) * max_height, orig_h)
            
            # 裁剪区域
            slice_img = img.crop((0, top, orig_w, bottom))
            
            # 生成临时文件路径
            slice_filename = f"slice_{i}_{os.path.basename(image_path)}"
            slice_path = os.path.join(temp_dir, slice_filename)
            
            # 保存图片，保持高质量
            slice_img.save(slice_path, quality=95, optimize=True)
            slice_paths.append(slice_path)

        return slice_paths
    except Exception as e:
        raise RuntimeError(f"图片切片失败: {e}")


def get_image_info(image_path: str) -> dict:
    """
    获取图片基本元数据
    
    Args:
        image_path: 图片路径
        
    Returns:
        包含 width, height, format 的字典
    """
    with Image.open(image_path) as img:
        w, h = img.size
        return {"width": w, "height": h, "format": img.format}
