"""
PPT/PPTX 解析模块
方案1（优先）: LibreOffice soffice 渲染（最高保真，所有形状+文字）
方案2（备用）: python-pptx 提取嵌入图片
"""
from typing import List
from PIL import Image
import io
import os
import subprocess
import shutil
import tempfile
from pathlib import Path

from pptx import Presentation


def _emu_to_px(emu: int, dpi: int = 150) -> int:
    return int(emu / 914400 * dpi)


def _try_soffice_render(pptx_path: str, dpi: int = 150) -> List[Image.Image] | None:
    """
    方案1：LibreOffice soffice 将每页导出为 PNG（保真度最高）
    """
    soffice = shutil.which("soffice") or shutil.which("soffice.exe")
    if soffice is None:
        return None

    temp_dir = tempfile.mkdtemp(prefix="pptx_render_")
    try:
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "png",
             "--outdir", temp_dir, pptx_path],
            capture_output=True, timeout=120
        )
        if result.returncode != 0:
            return None

        png_files = sorted(Path(temp_dir).glob("*.png"), key=lambda p: p.stem)
        if not png_files:
            return None

        images = []
        for f in png_files:
            img = Image.open(f).convert("RGB")
            scale = dpi / 96  # soffice 默认 96dpi
            if scale != 1.0:
                img = img.resize((int(img.width * scale), int(img.height * scale)),
                                  Image.Resampling.LANCZOS)
            images.append(img)
        return images
    except Exception:
        return None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _try_pptx_extract(pptx_path: str, dpi: int = 150) -> List[Image.Image]:
    """方案2：python-pptx 提取嵌入图片（适合内容全为图片的PPT）"""
    prs = Presentation(pptx_path)
    px_w = _emu_to_px(prs.slide_width, dpi)
    px_h = _emu_to_px(prs.slide_height, dpi)

    images: List[Image.Image] = []
    for slide in prs.slides:
        canvas = Image.new("RGB", (px_w, px_h), (255, 255, 255))
        for shape in slide.shapes:
            if not hasattr(shape, "image"):
                continue
            try:
                blob = shape.image.blob
                img = Image.open(io.BytesIO(blob)).convert("RGB")
                left = _emu_to_px(shape.left, dpi)
                top = _emu_to_px(shape.top, dpi)
                width = _emu_to_px(shape.width, dpi)
                height = _emu_to_px(shape.height, dpi)
                if width > 0 and height > 0:
                    img = img.resize((width, height), Image.Resampling.LANCZOS)
                    canvas.paste(img, (left, top))
            except Exception:
                pass
        images.append(canvas)
    return images


def pptx_to_images(pptx_path: str, dpi: int = 150) -> List[Image.Image]:
    """
    将 PPT/PPTX 每页渲染为 PIL Image，
    优先 soffice（保真），备用 python-pptx（提取嵌入图片）。

    Args:
        pptx_path: PPT/PPTX 文件路径
        dpi: 渲染分辨率，默认 150

    Returns:
        PIL Image 对象列表
    """
    # 方案1: soffice 渲染
    images = _try_soffice_render(pptx_path, dpi)
    if images:
        return images

    # 方案2: python-pptx 提取
    return _try_pptx_extract(pptx_path, dpi)