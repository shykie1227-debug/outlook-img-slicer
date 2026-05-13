"""
PPT/PPTX 解析模块
将 PPT/PPTX 每页渲染为 PIL Image，渲染后像普通图片一样走 detect_and_slice 切片。

方案优先级：
  1. PowerPoint COM（Windows + Office）—— 最高保真，渲染所见即所得
  2. LibreOffice soffice（跨平台）—— 形状/文字均可，保持次高保真
  3. python-pptx（纯 Python 备选）—— 仅提取嵌入图片，内容缺失，仅作最后兜底
"""
from typing import List
from PIL import Image
import io
import os
import subprocess
import shutil
import tempfile
import sys
from pathlib import Path

from pptx import Presentation


def _emu_to_px(emu: int, dpi: int = 150) -> int:
    return int(emu / 914400 * dpi)


# ────────────────────────────────────────────
# 方案 1：PowerPoint COM 导出（最优解）
# ────────────────────────────────────────────
def _try_powerpoint_export(pptx_path: str, dpi: int = 150) -> List[Image.Image] | None:
    """
    通过 PowerPoint COM 将每页导出为 PNG/RTF，
    再用 Pillow 读取。保真度最高，100% 再现幻灯片所有内容。
    """
    if sys.platform != "win32":
        return None

    try:
        import win32com.client
        import pythoncom
    except ImportError:
        return None

    temp_dir = tempfile.mkdtemp(prefix="pptx_render_")
    try:
        pythoncom.CoInitialize()
        ppt_app = win32com.client.Dispatch("PowerPoint.Application")
        ppt_app.Visible = 1  # 必须可见，否则部分主题渲染异常

        try:
            # 打开文件（ReadOnly=msc: -1=msoTrue）
            presentation = ppt_app.Presentations.Open(
                os.path.abspath(pptx_path),
                ReadOnly=True,
                WithWindow=False,
                # msoTrue = -1, msoFalse = 0
            )

            # 导出分辨率：PowerPoint 内部用 Points，1pt = 1/72 inch
            # dpi=150 → scale = 150/72 ≈ 2.08
            # dpi=200 → scale ≈ 2.78
            scale = dpi / 72.0
            pp_shape_size = 2      # ppShapeSizeDesiredScreen = 2
            pp_clip = 2            # ppClipFrame = 2

            temp_png_dir = tempfile.mkdtemp(prefix="pptx_png_")
            for i, slide in enumerate(presentation.Slides):
                slide_index = i + 1
                out_path = os.path.join(temp_png_dir, f"slide_{slide_index:03d}.png")
                # Export 返回 bool（非路径），文件已直接写到 out_path
                slide.Export(
                    out_path,
                    FilterName="PNG",
                    ScaleWidth=0,   # 0 = 保持原尺寸（按 ScaleHeight 等比）
                    ScaleHeight=0,
                )

            presentation.Close()
        finally:
            ppt_app.Quit()
            pythoncom.CoUninitialize()

        png_files = sorted(Path(temp_png_dir).glob("*.png"), key=lambda p: int(p.stem.split("_")[1]))
        if not png_files:
            shutil.rmtree(temp_png_dir, ignore_errors=True)
            return None

        images = []
        for f in png_files:
            img = Image.open(f).convert("RGB")
            # soffice/powerpoint 默认 96dpi，统一到目标 dpi
            if dpi != 96:
                new_w = int(img.width * dpi / 96)
                new_h = int(img.height * dpi / 96)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            images.append(img)
            f.unlink()  # 删除临时 PNG
        shutil.rmtree(temp_png_dir, ignore_errors=True)
        return images

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None


# ────────────────────────────────────────────
# 方案 2：LibreOffice soffice（跨平台保真）
# ────────────────────────────────────────────
def _try_soffice_render(pptx_path: str, dpi: int = 150) -> List[Image.Image] | None:
    """
    soffice --headless --convert-to png 将每页导出为 PNG。
    优点：跨平台，形状/文字渲染好。
    缺点：需要安装 LibreOffice，部分复杂动画效果略逊于 PowerPoint。
    """
    soffice = shutil.which("soffice") or shutil.which("soffice.exe")
    if soffice is None:
        return None

    temp_dir = tempfile.mkdtemp(prefix="pptx_render_")
    try:
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "png",
             "--outdir", temp_dir, pptx_path],
            capture_output=True, timeout=180
        )
        if result.returncode != 0:
            return None

        png_files = sorted(Path(temp_dir).glob("*.png"), key=lambda p: p.stem)
        if not png_files:
            return None

        images = []
        for f in png_files:
            img = Image.open(f).convert("RGB")
            # soffice 默认 96dpi → 等比缩放到目标 dpi
            if dpi != 96:
                new_w = int(img.width * dpi / 96)
                new_h = int(img.height * dpi / 96)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            images.append(img)
        return images
    except Exception:
        return None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ────────────────────────────────────────────
# 方案 3：python-pptx 提取（仅作最后兜底）
# ⚠️ 注意：此方案仅能提取「嵌入图片」，文字/形状/SmartArt 均会丢失。
#         仅在既无 Office 又无 LibreOffice 时使用。
# ────────────────────────────────────────────
def _try_pptx_extract(pptx_path: str, dpi: int = 150) -> List[Image.Image]:
    """
    python-pptx 提取嵌入图片并拼回幻灯片画布。
    ⚠️ 内容缺失警告：文字、形状、SmartArt、艺术字 均不会出现在输出中。
    """
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


# ────────────────────────────────────────────
# 主入口
# ────────────────────────────────────────────
def pptx_to_images(pptx_path: str, dpi: int = 150) -> List[Image.Image]:
    """
    将 PPT/PPTX 每页渲染为 PIL Image。
    优先 PowerPoint COM（Windows + Office）→ LibreOffice soffice → python-pptx（兜底）。

    Args:
        pptx_path: PPT/PPTX 文件路径
        dpi: 渲染分辨率，默认 150（数值越高越清晰，也越慢）

    Returns:
        PIL Image 对象列表，每项对应一页幻灯片
    """
    # 方案 1：PowerPoint COM（最优）
    images = _try_powerpoint_export(pptx_path, dpi)
    if images:
        return images

    # 方案 2：LibreOffice soffice
    images = _try_soffice_render(pptx_path, dpi)
    if images:
        return images

    # 方案 3：python-pptx（最后兜底，内容可能缺失）
    # 此处打印警告，方便用户排查
    print("[警告] PPT 解析使用了 python-pptx 方案，"
          "仅能提取嵌入图片，文字/形状/SmartArt 内容可能丢失。"
          "建议在 Windows 上安装 Microsoft PowerPoint 以获得完整保真渲染。")
    return _try_pptx_extract(pptx_path, dpi)
