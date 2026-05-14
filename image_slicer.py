"""
图像切片器模块
将长图按指定高度切片，支持 JPG/PNG/BMP/WebP/GIF
V4.4 智能切图：通过像素灰度方差 + 亮度综合分析查找安全断点，规避文字区
"""
import os
import tempfile
from math import ceil, floor
from typing import List
from pathlib import Path
from PIL import Image

from image_safety import check_image_safety, ImageSafetyError


# ── 智能切图常量 ────────────────────────────
SMART_SCAN_RATIO = 0.15       # 扫描窗口 = 切片高度 * 此比率（自适应）
SMART_MIN_SCAN = 30           # 扫描窗口最小 px
SMART_MAX_SCAN = 200          # 扫描窗口最大 px
SMART_MIN_SPACING = 6         # 至少连续 N 行空白才算安全断点
BLANK_VARIANCE_THRESHOLD = 8  # 灰度标准差 < 此值视为"行内无变量"（空白/纯色行）
BLANK_BRIGHTNESS_MIN = 200    # 空白行平均亮度下限（排除深色纯色区）
TEXTURE_VARIANCE_MIN = 15     # 文字行灰度标准差下限（防止误判灰度不均的图片为文字）

# 动态亮度阈值：低于此亮度视为"非空白"
# 若图像整体偏暗，使用自适应 percentile
ADAPTIVE_BRIGHTNESS_PERCENTILE = 85  # 取全图亮度百分位作为动态阈值


def _row_stats(pixels, y: int, width: int) -> tuple:
    """
    分析第 y 行的像素统计量。

    Returns:
        (mean_brightness, std_dev, sample_count)
        mean_brightness: 平均亮度（0-255）
        std_dev: 灰度标准差，反映行内纹理复杂度
        sample_count: 采样点数
    """
    # 密集采样：每隔 2px 取一点，上限 150 个点
    step = max(1, width // 150)
    values: List[int] = []
    for x in range(0, width, step):
        try:
            p = pixels[x, y]
            if isinstance(p, tuple) and len(p) >= 3:
                # RGB → 灰度亮度（加权）
                gray = int(0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2])
                values.append(gray)
            else:
                values.append(int(p))
        except (IndexError, TypeError):
            pass

    if not values:
        return (255, 0, 0)

    mean = sum(values) / len(values)
    if len(values) >= 2:
        var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        std = var ** 0.5
    else:
        std = 0.0

    return (mean, std, len(values))


def _is_safe_blank(pixels, y: int, width: int, adaptive_threshold: float = 220) -> bool:
    """
    判断第 y 行是否为"安全的空白行"（可在此处切图）。

    双条件：
    1. 亮度足够高（背景色），排除深色纯色区
    2. 灰度方差足够低（无纹理），排除文字/图片/线条

    Args:
        pixels: 像素加载器
        y: 行坐标
        width: 图片宽度
        adaptive_threshold: 动态亮度阈值（基于全图统计）

    Returns:
        True 表示该行适合切片
    """
    mean_brightness, std_dev, samples = _row_stats(pixels, y, width)
    if samples < 5:
        return False

    # 条件 1：亮度必须高于动态阈值（排除深色背景的内容）
    if mean_brightness < adaptive_threshold:
        return False

    # 条件 2：灰度方差必须足够低（排除有文字/线条/纹理的行）
    if std_dev > BLANK_VARIANCE_THRESHOLD:
        return False

    return True


def _compute_adaptive_threshold(pixels, width: int, height: int) -> float:
    """
    计算图像的动态亮度阈值。
    取全图各行的平均亮度的第 ADAPTIVE_BRIGHTNESS_PERCENTILE 百分位。
    """
    step_y = max(1, height // 50)  # 采样 ~50 行
    step_x = max(1, width // 10)   # 每行采 ~10 点
    all_means: List[float] = []

    for y in range(0, height, step_y):
        values: List[int] = []
        for x in range(0, width, step_x):
            try:
                p = pixels[x, y]
                if isinstance(p, tuple) and len(p) >= 3:
                    gray = int(0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2])
                    values.append(gray)
                else:
                    values.append(int(p))
            except (IndexError, TypeError):
                pass
        if values:
            all_means.append(sum(values) / len(values))

    if not all_means:
        return BLANK_BRIGHTNESS_MIN

    all_means.sort()
    idx = int(len(all_means) * ADAPTIVE_BRIGHTNESS_PERCENTILE / 100)
    idx = min(idx, len(all_means) - 1)
    return max(all_means[idx], BLANK_BRIGHTNESS_MIN)


def _find_smart_cut(pixels, width: int, height: int, target_cut: int,
                    slice_height: int) -> int:
    """
    在 target_cut 附近查找最佳切片位置。

    算法：
    1. 计算扫描窗口（基于 slice_height 自适应）
    2. 从 target_cut 向外双向扫描，寻找连续安全空白行
    3. 评分综合考量：空白行长度、距目标点的距离、对称性
    4. 返回最适合切片的 y 坐标

    Args:
        pixels: 像素加载器
        width: 图片宽度
        height: 图片高度
        target_cut: 理论等分切割位置
        slice_height: 单切片高度，用于计算扫描范围

    Returns:
        最佳切割位置的 y 坐标
    """
    scan = int(max(SMART_MIN_SCAN, min(SMART_MAX_SCAN, slice_height * SMART_SCAN_RATIO)))
    scan_top = max(0, target_cut - scan)
    scan_bottom = min(height, target_cut + scan)

    # 先计算全图像亮度自适应阈值
    adaptive_threshold = _compute_adaptive_threshold(pixels, width, height)

    best_cut = target_cut
    best_score = -1.0

    y = scan_top
    while y < scan_bottom:
        if _is_safe_blank(pixels, y, width, adaptive_threshold):
            # 计算连续安全空白行
            streak = 0
            yy = y
            while yy < scan_bottom and _is_safe_blank(pixels, yy, width, adaptive_threshold):
                streak += 1
                yy += 1

            if streak >= SMART_MIN_SPACING:
                # 选择连续空白行的中间位置作为切割点
                cut_pos = y + streak // 2

                # ── 评分公式 ──
                #  空白行越多越好，越靠近 target_cut 越好
                #  权重：空白行数 (×2) + 距离惩罚 (负，×0.2)
                dist = abs(cut_pos - target_cut)
                score = (streak * 2.0) - (dist * 0.2)

                if score > best_score:
                    best_score = score
                    best_cut = cut_pos

            y = yy  # 跳过已扫描的连续行
        else:
            y += 1

    return best_cut


def detect_and_slice(image_path: str, max_height: int = 1200,
                     smart: bool = False, target_width: int = None) -> List[str]:
    """
    检测图像高度，必要时进行无损切片。

    Args:
        image_path: 原始图片文件路径
        max_height: 单片最大高度（像素），默认 1200px
        smart: 是否启用智能切图（避免切断内容），默认 False=等分切图
        target_width: 目标宽度（像素），若指定则在切片前将图片缩放到此宽度，None=保持原宽

    Returns:
        切片后的临时文件路径列表
    """
    try:
        check_image_safety(image_path)
    except ImageSafetyError:
        pass

    try:
        img = Image.open(image_path)
        orig_w, orig_h = img.size

        # ── 等比缩放到目标宽度（如果指定） ──────────────────────────────
        if target_width and 0 < target_width < orig_w:
            ratio = target_width / orig_w
            new_h = int(orig_h * ratio)
            img = img.resize((target_width, new_h), Image.LANCZOS)
            orig_w, orig_h = img.size

        if orig_h <= max_height:
            return [image_path]

        slice_count = ceil(orig_h / max_height)
        slice_height = floor(orig_h / slice_count)

        original_ext = Path(image_path).suffix.lower()
        preserve_alpha = original_ext in (".png", ".gif") and img.mode == "RGBA"

        # ── 如果启用智能切图，预扫像素 ──────────────────────────────────
        pixels = None
        if smart:
            try:
                scan_img = img.convert("RGB") if img.mode != "RGB" else img
                pixels = scan_img.load()
            except Exception:
                pixels = None

        slice_paths: List[str] = []
        temp_dir = tempfile.gettempdir()
        base_name = Path(image_path).stem

        for i in range(slice_count):
            top = i * slice_height
            bottom = (top + slice_height) if i < slice_count - 1 else orig_h

            # 智能切图：在断点附近找连续安全空白行
            if smart and pixels and i < slice_count - 1:
                adjusted = _find_smart_cut(pixels, orig_w, orig_h, bottom, slice_height)
                # 安全网：调整不能使最后一片过高
                max_adjust = int(slice_height * 1.3)
                if adjusted > top + max_adjust:
                    adjusted = bottom
                bottom = adjusted

            # 裁剪区域（使用经过缩放的 orig_w）
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
            new_canvas.paste(canvas, ((w - canvas.width) // 2, 0))
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
