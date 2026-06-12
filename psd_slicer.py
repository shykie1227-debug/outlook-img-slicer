"""
PSD / PSB 解析模块
将 Photoshop 文档展平为单张 PIL Image（自动合成所有可见图层），再走和普通图片一样的切片流程。

核心思路：psd-tools 提供 PSDImage.composite()，直接按 Photoshop「合并可见图层」的方式
渲染成 PIL Image，文字、形状、图层蒙版、混合模式都会被正确合成。

支持格式：
  - .psd（Photoshop Document）—— 最大 30,000×30,000 像素
  - .psb（Photoshop Large Document Format）—— 最大 300,000×300,000 像素
两种格式文件头都是 '8BPS'，psd-tools 透明处理，代码逻辑相同。

依赖提示：psd_tools 内部依赖 numpy（仅在运行时需要，不在顶层 import 以避免
主程序未用 PSD 功能时启动报错）。本模块通过 _ensure_dependencies() 懒加载验证。
"""
from typing import List
from pathlib import Path
from PIL import Image

_PSDImage = None  # 懒加载，模块导入时不去强求 psd_tools/numpy


def _ensure_dependencies():
    """
    首次调用时验证依赖是否可用，缺失时给出针对性提示。
    放在函数内而不是模块顶部，是为了避免主程序未使用 PSD 时连带启动失败。
    """
    global _PSDImage
    if _PSDImage is not None:
        return _PSDImage
    try:
        from psd_tools import PSDImage as _PSDI
        _PSDImage = _PSDI
        return _PSDImage
    except ImportError as e:
        missing = []
        if "numpy" in str(e).lower() or "No module named 'numpy'" in str(e):
            missing.append("numpy")
        if "psd_tools" in str(e).lower() or "No module named 'psd_tools'" in str(e):
            missing.append("psd-tools")
        if not missing:
            missing.append("psd-tools / numpy")
        raise ImportError(
            "PSD 支持需要额外依赖，请运行以下命令安装后重启程序：\n"
            f"  pip install {' '.join(missing)}\n"
            f"原始错误: {e}"
        )


def _load_psd(psd_path: str):
    """打开 PSD/PSB 文件并做基本校验。"""
    PSDImage = _ensure_dependencies()
    ext = Path(psd_path).suffix.lower()
    if ext not in (".psd", ".psb"):
        raise ValueError(f"不是有效的 PSD/PSB 文件: {psd_path}")
    try:
        return PSDImage.open(psd_path)
    except Exception as e:
        raise RuntimeError(f"PSD/PSB 文件解析失败: {e}")


def psd_to_images(psd_path: str, dpi: int = 150) -> List[Image.Image]:
    """
    将 PSD 文档展平为 PIL Image 列表（单页返回 [img]，多页返回多张）。

    Args:
        psd_path: PSD 文件路径
        dpi: 保留参数，与 pdf_slicer/ppt_slicer 保持接口一致
             （psd-tools 使用 PSD 内部像素尺寸，DPI 概念不直接适用）

    Returns:
        PIL Image 对象列表（通常长度=1，因为 PSD 是单文档多图层格式）
    """
    psd = _load_psd(psd_path)

    try:
        # composite() 按 Photoshop「合并可见图层」方式渲染
        # psd-tools 1.10+ 返回带 alpha 的 RGBA Image，需转 RGB 供切片
        flat = psd.composite()
        if flat is None:
            raise RuntimeError("PSD 文件未包含任何可渲染图层。")
        if flat.mode == "RGBA":
            # 白底合成（与 PowerPoint/Word 默认背景一致）
            bg = Image.new("RGB", flat.size, (255, 255, 255))
            bg.paste(flat, mask=flat.split()[3])
            flat = bg
        elif flat.mode != "RGB":
            flat = flat.convert("RGB")
        return [flat]
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"PSD 渲染失败: {e}")
