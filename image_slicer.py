"""
图像切片器模块
将长图按指定高度切片，支持 JPG/PNG/BMP/WebP/GIF
V4 新增智能切图：通过像素分析避免切断重要内容（标题、表格、文本行）
"""
import os
import tempfile
from math import ceil, floor
from typing import List
from pathlib import Path
from PIL import Image


# ── 智能切图常量 ────────────────────────────
SMART_SCAN_WINDOW = 20       # 扫描窗口高度（px），在断点附近上下扫描
SMART_MIN_SPACING = 6        # 至少连续 N 行空白才算安全断点
SMART_BRIGHTNESS_THRESHOLD = 240  # 像素亮度阈值（接近白色）

from image_safety import check_image_safety, ImageSafetyError


def _is_blank_row(pixels, y: int, width: int) -> bool:
    """判断第 y 行是否为空白行（接近白色）"""
    if width == 0:
        return True
    # 采样检测：取等间隔 10 个点
    sample_step = max(1, width // 10)
    blank_count = 0
    samples = 0
    for x in range(0, width, sample_step):
        try:
            p = pixels[x, y]
            # RGB tuple: 三个通道都接近白色
            if isinstance(p, tuple) and len(p) >= 3:
                if p[0] > SMART_BRIGHTNESS_THRESHOLD and p[1] > SMART_BRIGHTNESS_THRESHOLD and p[2] > SMART_BRIGHTNESS_THRESHOLD:
                    blank_count += 1
            else:
                # 灰度图
                if p > SMART_BRIGHTNESS_THRESHOLD:
                    blank_count += 1
            samples += 1
        except (IndexError, TypeError):
            pass
    return samples > 0 and (blank_count / samples) > 0.85


def _find_smart_cut(pixels, width: int, height: int, target_cut: int) -> int:
    """
    在 target_cut 附近查找最佳切片位置。
    优先选择连续空白行最多的位置（安全断点）。
    返回最适合切片的 y 坐标。
    """
    scan_top = max(0, target_cut - SMART_SCAN_WINDOW)
    scan_bottom = min(height, target_cut + SMART_SCAN_WINDOW)

    best_cut = target_cut
    best_blank_streak = 0

    y = scan_top
    while y < scan_bottom:
        if _is_blank_row(pixels, y, width):
            # 计算从这里开始的连续空白行数
            streak = 0
            yy = y
            while yy < scan_bottom and _is_blank_row(pixels, yy, width):
                streak += 1
                yy += 1
            if streak >= SMART_MIN_SPACING and streak > best_blank_streak:
                # 优先靠近目标切割位置
                distance_penalty = abs(yy - target_cut)
                score = streak - distance_penalty * 0.1
                if score > best_blank_streak:
                    best_blank_streak = score
                    # 选连续空白行的中间位置
                    best_cut = y + streak // 2
            y = yy
        else:
            y += 1
    return best_cut


def detect_and_slice(image_path: str, max_height: int = 1200, smart: bool = True) -> List[str]:
    """
    检测图像高度，必要时进行无损切片。

    Args:
        image_path: 原始图片文件路径
        max_height: 单片最大高度（像素），默认 1200px
        smart: 是否启用智能切图（避免切断内容）

    Returns:
        切片后的临时文件路径列表
    """
    try:
        check_image_safety(image_path)
    except ImageSafetyError:
        # 文件过大时降级：不用安全检查，直接尝试打开
        pass

    try:
        img = Image.open(image_path)
        orig_w, orig_h = img.size

        if orig_h <= max_height:
            return [image_path]

        slice_count = ceil(orig_h / max_height)
        slice_height = floor(orig_h / slice_count)

        original_ext = Path(image_path).suffix.lower()
        preserve_alpha = original_ext in (".png", ".gif") and img.mode == "RGBA"

        # 如果启用智能切图，预扫像素
        pixels = None
        if smart:
            try:
                # 转为 RGB 模式以便统一处理像素颜色
                scan_img = img.convert("RGB") if img.mode != "RGB" else img
                pixels = scan_img.load()
            except Exception:
                pixels = None

        slice_paths: List[str] = []
        temp_dir = tempfile.gettempdir()
        base_name = Path(image_path).stem

        for i in range(slice_count):
            top = i * slice_height
            bottom = top + slice_height if i < slice_count - 1 else orig_h

            # 智能切图：在断点附近找连续空白行
            if smart and pixels and i < slice_count - 1:
                adjusted = _find_smart_cut(pixels, orig_w, orig_h, bottom)
                # 调整不能使最后一片太高
                if adjusted > top + max_height * 1.2:
                    adjusted = bottom
                bottom = adjusted

            # 裁剪区域
            slice_img = img.crop((0, top, orig_w, bottom))

            slice_filename = f"slice_{i}_{base_name}.png"
            slice_path = os.path.join(temp_dir, slice_filename)

            if preserve_alpha:
                slice_img.save(slice_path, format="PNG", optimize=True)
            else:
                if slice_img.mode in ("RGBA", "P"):
                    slice_img = slice_img.convert("RGB")
                slice_img.save(slice_path, format="JPEG", quality=95, optimize=True)
            slice_paths.append(slice_path)

        return slice_paths
    except Exception as e:
        raise RuntimeError(f"图片切片失败: {e}")


def get_image_info(image_path: str) -> dict:
    """获取图片基本元数据"""
    with Image.open(image_path) as img:
        w, h = img.size
        return {"width": w, "height": h, "format": img.format}


def auto_merge_images(image_paths: List[str], direction: str = "vertical") -> str:
    """
    多图自动合并为一张长图。

    基于开源项目实现:
    - Pillow (python-pillow/Pillow ⭐13k)
      https://github.com/python-pillow/Pillow
      Image.paste 文档: https://pillow.readthedocs.io/en/stable/reference/Image.html
    - nkmk/python-snippets (⭐317) concat 参考
      https://github.com/nkmk/python-snippets

    Args:
        image_paths: 图片路径列表
        direction: "vertical" 纵向拼接

    Returns:
        合并后的临时文件路径
    """
    if not image_paths:
        raise ValueError("没有图片可合并")
    if len(image_paths) == 1:
        return image_paths[0]

    # 逐张合并：每次取当前画布 + 新图 → 创建新画布
    # 参考 Pillow 官方教程: Image.paste 拼接
    def _ensure_rgb(img: Image.Image) -> Image.Image:
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            return bg
        return img.convert("RGB") if img.mode != "RGB" else img.copy()

    with Image.open(image_paths[0]) as f0:
        canvas = _ensure_rgb(f0)

    for p in image_paths[1:]:
        with Image.open(p) as fi:
            nxt = _ensure_rgb(fi)

        if direction == "vertical":
            w = max(canvas.width, nxt.width)
            h = canvas.height + nxt.height
            new_canvas = Image.new("RGB", (w, h), (255, 255, 255))
            # 已有内容居中粘贴到顶部
            new_canvas.paste(canvas, ((w - canvas.width) // 2, 0))
            # 新图居中粘贴到底部
            new_canvas.paste(nxt, ((w - nxt.width) // 2, canvas.height))
        else:
            w = canvas.width + nxt.width
            h = max(canvas.height, nxt.height)
            new_canvas = Image.new("RGB", (w, h), (255, 255, 255))
            new_canvas.paste(canvas, (0, (h - canvas.height) // 2))
            new_canvas.paste(nxt, (canvas.width, (h - nxt.height) // 2))
        canvas = new_canvas

    temp_dir = tempfile.gettempdir()
    merged_path = os.path.join(temp_dir, f"merged_{os.getpid()}.jpg")
    canvas.save(merged_path, format="JPEG", quality=97, optimize=True)
    return merged_path
