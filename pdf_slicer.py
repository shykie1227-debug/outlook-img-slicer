"""
PDF 解析器模块
使用 PyMuPDF 将 PDF 页面转换为图片
"""

import io
from typing import List
from PIL import Image
import fitz  # PyMuPDF


def pdf_to_images(pdf_path: str, dpi: int = 150) -> List[Image.Image]:
    """
    将 PDF 转换为 PIL Image 列表

    Args:
        pdf_path: PDF 文件路径
        dpi: 渲染分辨率，默认 150

    Returns:
        PIL Image 对象列表（每页一张图）
    """
    images: List[Image.Image] = []
    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc[page_num]
        # 计算缩放因子 (72 DPI 基准)
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # 转换为 RGB 并加载为 PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        if img.mode != "RGB":
            img = img.convert("RGB")
        images.append(img)

    doc.close()
    return images


def pdf_page_count(pdf_path: str) -> int:
    """获取 PDF 页数"""
    doc = fitz.open(pdf_path)
    count = len(doc)
    doc.close()
    return count
