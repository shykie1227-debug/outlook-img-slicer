"""
PPT/PPTX 解析模块
V2: 简化为纯 PyMuPDF 直接渲染，修复图片叠加导致的崩溃问题。
PyMuPDF 会自动处理嵌入图片，不手工解析 XML。
"""
from typing import List
from PIL import Image
import fitz  # PyMuPDF
import io


def pptx_to_images(pptx_path: str, dpi: int = 150) -> List[Image.Image]:
    """
    将 PPT/PPTX 每页幻灯片渲染为 PIL Image 对象。

    Args:
        pptx_path: PPT/PPTX 文件路径
        dpi: 渲染分辨率，默认 150

    Returns:
        PIL Image 对象列表
    """
    images: List[Image.Image] = []
    doc = None

    try:
        doc = fitz.open(pptx_path)
        total_pages = len(doc)

        if total_pages == 0:
            raise RuntimeError("PPT 文件为空，未找到任何幻灯片页面")

        zoom = dpi / 72.0

        for page_num in range(total_pages):
            page = doc[page_num]

            # 直接渲染整页（文字+图片+矢量 一次完成，不再手工叠加）
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            # 确保 RGB 模式
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")

            images.append(img)

        return images

    except Exception as e:
        raise RuntimeError(f"PPT 渲染失败: {e}")
    finally:
        if doc:
            doc.close()