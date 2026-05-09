"""
PPT/PPTX 解析模块
使用 PyMuPDF (fitz) 将 PPT/PPTX 每页幻灯片渲染为高分辨率 PIL Image

注意：PyMuPDF 对 PPTX 的渲染支持比 PPT 更完整。
PPTX（.pptx）格式基于 Office Open XML（ZIP 压缩的 XML），PyMuPDF 可直接读取并渲染。
PP（.ppt）二进制格式支持有限，若用户有强需求建议用 LibreOffice 转换。
"""
from typing import List
from PIL import Image
import fitz  # PyMuPDF
import io


def pptx_to_images(pptx_path: str, dpi: int = 150) -> List[Image.Image]:
    """
    将 PPT/PPTX 每页幻灯片渲染为 PIL Image 对象

    Args:
        pptx_path: PPT/PPTX 文件路径
        dpi: 渲染分辨率（每英寸点数），默认 150。
             推荐值：72（屏幕）、150（邮件）、300（打印）
             DPI 越高图片越清晰，但内存占用和文件体积也会增大。

    Returns:
        PIL Image 对象列表，每张对应一页幻灯片
    """
    images: List[Image.Image] = []
    doc = None
    try:
        doc = fitz.open(pptx_path)
        total_pages = len(doc)

        if total_pages == 0:
            raise RuntimeError("PPT 文件为空，未找到任何幻灯片页面")

        for page_num in range(total_pages):
            page = doc[page_num]

            # 计算缩放比例（72 是 PDF/PPTX 的标准屏幕 DPI）
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)

            # 渲染页面为像素图（支持 PPTX 中的矢量图形、文本、图片）
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # 转换为 PNG 字节流，再转为 PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))

            # 确保图片是 RGB 模式（去除 alpha 通道，确保兼容邮件插入）
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")

            images.append(img)

        return images

    except Exception as e:
        raise RuntimeError(f"PPT 解析失败: {e}")
    finally:
        if doc:
            doc.close()
