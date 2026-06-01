"""
PSD 解析模块
将 PSD 文档展平为单张 PIL Image（自动合成所有可见图层），再走和普通图片一样的切片流程。

核心思路：psd-tools 提供 PSDImage.composite()，直接按 Photoshop「合并可见图层」的方式
渲染成 PIL Image，文字、形状、图层蒙版、混合模式都会被正确合成。

支持格式：.psd（Photoshop Document）
不支持：.psb（Large Document Format）—— 提示用户先在 Photoshop 另存为 PSD
"""
from typing import List
from PIL import Image

try:
    from psd_tools import PSDImage
except ImportError as e:
    raise ImportError(
        "缺少 psd-tools 库，请运行 'pip install psd-tools' 安装。"
        f"原始错误: {e}"
    )


def _load_psd(psd_path: str) -> PSDImage:
    """打开 PSD 文件并做基本校验。"""
    if not psd_path.lower().endswith(".psd"):
        raise ValueError(f"不是有效的 PSD 文件: {psd_path}")
    try:
        return PSDImage.open(psd_path)
    except Exception as e:
        raise RuntimeError(f"PSD 文件解析失败: {e}")


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


def get_psd_info(psd_path: str) -> dict:
    """获取 PSD 基本元数据（用于调试/日志）。"""
    psd = _load_psd(psd_path)
    return {
        "width": psd.width,
        "height": psd.height,
        "layers": len(list(psd)),
        "color_mode": str(psd.color_mode),
    }
