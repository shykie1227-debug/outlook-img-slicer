"""
PPT/PPTX 解析模块
将 PPT/PPTX 每页渲染为 PIL Image，渲染后像普通图片一样走 detect_and_slice 切片。

方案优先级：
  1. PowerPoint COM（Windows + Office）—— 最高保真，渲染所见即所得
  2. LibreOffice soffice（跨平台）—— 形状/文字均可，保持次高保真
  （python-pptx 兜底已移除：只能提取嵌入图片，文字/形状丢失，Windows 上用户强制走 COM）
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

# python-pptx 仅在 soffice 和 COM 都不存在时作为极端兜底，懒加载
_presentation = None


def _ensure_pptx():
    global _presentation
    if _presentation is not None:
        return _presentation
    try:
        from pptx import Presentation
        _presentation = Presentation
        return _presentation
    except ImportError:
        return None


PPT_RENDERER_UNAVAILABLE_HINT = (
    "当前环境没有可用的高保真 PPT 渲染器，已停止导出以避免文字、形状或 SmartArt 被改写。\n\n"
    "可用处理方式：\n"
    "1. Windows：安装 Microsoft PowerPoint，程序将优先使用 PowerPoint COM 渲染。\n"
    "2. macOS / Linux：安装 LibreOffice，程序将使用 soffice 转 PDF 后逐页渲染。"
)


def _emu_to_px(emu: int, dpi: int = 150) -> int:
    return int(emu / 914400 * dpi)


# ────────────────────────────────────────────
# 方案 1：PowerPoint COM 导出（最优解）
# ────────────────────────────────────────────
def _try_powerpoint_export(pptx_path: str, dpi: int = 150):
    """
    通过 PowerPoint COM 将每页导出为 PNG，
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
            presentation = ppt_app.Presentations.Open(
                os.path.abspath(pptx_path),
                ReadOnly=True,
                WithWindow=False,
            )

            temp_png_dir = tempfile.mkdtemp(prefix="pptx_png_")
            for i, slide in enumerate(presentation.Slides):
                slide_index = i + 1
                out_path = os.path.join(temp_png_dir, f"slide_{slide_index:03d}.png")
                slide.Export(out_path, FilterName="PNG", ScaleWidth=0, ScaleHeight=0)

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
            if dpi != 96:
                new_w = int(img.width * dpi / 96)
                new_h = int(img.height * dpi / 96)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            images.append(img)
            f.unlink()
        shutil.rmtree(temp_png_dir, ignore_errors=True)
        return images

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None


# ────────────────────────────────────────────
# 方案 2：LibreOffice soffice（Windows 跨机保真）
# ────────────────────────────────────────────
def _find_soffice() -> str | None:
    r"""
    Windows 下查找 LibreOffice 可执行文件。
    常见安装路径：
      • 默认安装路径 C:\Program Files\LibreOffice\program\soffice.exe
      • 用户级安装   C:\Program Files (x86)\LibreOffice\program\soffice.exe
      • PATH 里的    soffice / soffice.exe
    """
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        r"C:\Program Files\LibreOffice\program\soffice.com",
        "soffice.exe", "soffice",
    ]
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return shutil.which("soffice") or shutil.which("soffice.exe")


def _soffice_export(pptx_path: str, outdir: str, target_format: str) -> bool:
    soffice = _find_soffice()
    if soffice is None:
        return False
    try:
        profile_dir = tempfile.mkdtemp(prefix="soffice_profile_")
        cmd = [
            soffice, "--headless", "--nologo", "--nofirststartwizard", "--norestore",
            f"-env:UserInstallation=file://{profile_dir}",
            "--convert-to", target_format,
            "--outdir", outdir,
            os.path.abspath(pptx_path),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=180, text=True)
        shutil.rmtree(profile_dir, ignore_errors=True)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _try_soffice_render(pptx_path: str, dpi: int = 150):
    if _find_soffice() is None:
        return None

    temp_dir = tempfile.mkdtemp(prefix="pptx_render_")
    try:
        if not _soffice_export(pptx_path, temp_dir, "pdf"):
            return None

        pdf_files = sorted(Path(temp_dir).glob("*.pdf"), key=lambda p: p.stem)
        if not pdf_files:
            return None

        images: List[Image.Image] = []
        try:
            import fitz
            for pdf_file in pdf_files:
                doc = fitz.open(str(pdf_file))
                try:
                    zoom = dpi / 72.0
                    mat = fitz.Matrix(zoom, zoom)
                    for page in doc:
                        pix = page.get_pixmap(matrix=mat, alpha=False)
                        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                        images.append(img)
                finally:
                    doc.close()
        except ImportError:
            try:
                from pdf2image import convert_from_path
                for pdf_file in pdf_files:
                    images.extend(convert_from_path(str(pdf_file), dpi=dpi))
            except Exception:
                return None

        if not images:
            return None
        return images
    except Exception:
        return None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ────────────────────────────────────────────
# 主入口
# ────────────────────────────────────────────
def pptx_to_images(pptx_path: str, dpi: int = 150) -> List[Image.Image]:
    """将 PPT/PPTX 每页渲染为 PIL Image。"""
    images = _try_powerpoint_export(pptx_path, dpi)
    if images:
        return images
    if sys.platform == "win32":
        raise RuntimeError(PPT_RENDERER_UNAVAILABLE_HINT)
    images = _try_soffice_render(pptx_path, dpi)
    if images:
        return images
    raise RuntimeError(PPT_RENDERER_UNAVAILABLE_HINT)
