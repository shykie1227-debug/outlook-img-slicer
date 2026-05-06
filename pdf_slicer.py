"""
PDF 解析模块
使用 PyMuPDF (fitz) 将 PDF 页面转换为高分辨率 PIL Image
优化说明：增加了 DPI 参数控制，平衡清晰度与处理速度。
"""
from typing import List
import fitz  # PyMuPDF
from PIL import Image
import io


def pdf_to_images(pdf_path: str, dpi: int = 150) -> List[Image.Image]:
    """
    将 PDF 所有页面渲染为 PIL Image 对象

    Args:
        pdf_path: PDF 文件路径
        dpi: 渲染分辨率（Dots Per Inch），默认 150。
             提高 DPI 可获得更清晰的图片，但会增加内存占用。

    Returns:
        PIL Image 对象列表
    """
    images = []
    doc = None
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # 计算缩放比例 (72 是 PDF 的标准 DPI)
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            
            # 渲染页面为像素图
            pix = page.get_pixmap(matrix=mat)
            
            # 转换为 PNG 字节流
            img_data = pix.tobytes("png")
            
            # 转换为 PIL Image
            img = Image.open(io.BytesIO(img_data))
            images.append(img)
            
    except Exception as e:
        raise RuntimeError(f"PDF 解析失败: {e}")
    finally:
        if doc:
            doc.close()
            
    return images
