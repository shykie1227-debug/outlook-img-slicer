"""
图像切片器模块
将长图按指定高度切片，支持 JPG/PNG/BMP/WebP/GIF
V4.4 智能切图：通过像素灰度方差 + 亮度综合分析查找安全断点，规避文字区
"""
import os
import tempfile
from math import ceil
from typing import List, Tuple
from pathlib import Path
from PIL import Image

from image_safety import check_image_safety, ImageSafetyError


# ── 智能切图常量 ────────────────────────────
SMART_SCAN_RATIO = 0.25       # 扫描窗口 = 切片高度 * 此比率（自适应）
SMART_MIN_SCAN = 60           # 扫描窗口最小 px
SMART_MAX_SCAN = 500          # 扫描窗口最大 px
SMART_MIN_SPACING = 12        # 至少连续 N 行空白才算安全断点
BLANK_VARIANCE_THRESHOLD = 10 # 灰度标准差 < 此值视为"行内无变量"（空白/纯色行）
BLANK_BRIGHTNESS_MIN = 180    # 空白行平均亮度下限（排除深色纯色区）
TEXTURE_VARIANCE_MIN = 12     # 文字行灰度标准差下限（防止误判灰度不均的图片为文字）

# 动态亮度阈值：低于此亮度视为"非空白"
# 若图像整体偏暗，使用自适应 percentile
ADAPTIVE_BRIGHTNESS_PERCENTILE = 85  # 取全图亮度百分位作为动态阈值


def _row_stats(pixels, y: int, width: int) -> Tuple[float, float, int, float]:
    """
    分析第 y 行的像素统计量。

    Returns:
        (mean_brightness, std_dev, sample_count, transition_ratio)
        mean_brightness: 平均亮度（0-255）
        std_dev: 灰度标准差，反映行内纹理复杂度
        sample_count: 采样点数
        transition_ratio: 相邻采样点的显著变化比例，文字/线条通常更高
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
        return (255, 0, 0, 0.0)

    mean = sum(values) / len(values)
    if len(values) >= 2:
        var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        std = var ** 0.5
    else:
        std = 0.0

    if len(values) >= 2:
        transitions = 0
        for idx in range(1, len(values)):
            if abs(values[idx] - values[idx - 1]) >= 12:
                transitions += 1
        transition_ratio = transitions / (len(values) - 1)
    else:
        transition_ratio = 0.0

    return (mean, std, len(values), transition_ratio)


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
    mean_brightness, std_dev, samples, transition_ratio = _row_stats(pixels, y, width)
    if samples < 5:
        return False

    # 条件 1：亮度必须高于动态阈值（排除深色背景的内容）
    if mean_brightness < adaptive_threshold:
        return False

    # 条件 2：灰度方差必须足够低（排除有文字/线条/纹理的行）
    if std_dev > BLANK_VARIANCE_THRESHOLD:
        return False

    if transition_ratio > 0.06:
        return False

    return True


def _is_text_like(mean_brightness: float, std_dev: float, transition_ratio: float) -> bool:
    """粗略识别文字/线条密集行，用于回退评分避开正文。"""
    if mean_brightness <= 35 or mean_brightness >= 252:
        return False
    return std_dev >= TEXTURE_VARIANCE_MIN and transition_ratio >= 0.12


def _row_content_score(pixels, y: int, width: int, adaptive_threshold: float) -> float:
    """
    计算一行作为切点的“内容风险”分数，越低越适合切图。

    没有找到真正空白带时，回退到低纹理、低过渡、较亮的行，
    尽量切在段落间距、留白、浅色块边界，而不是文字正文中间。
    """
    mean_brightness, std_dev, samples, transition_ratio = _row_stats(pixels, y, width)
    if samples < 5:
        return float("inf")

    brightness_penalty = max(0.0, adaptive_threshold - mean_brightness) * 1.5
    texture_penalty = std_dev * 3.5
    transition_penalty = transition_ratio * 120.0
    text_penalty = 80.0 if _is_text_like(mean_brightness, std_dev, transition_ratio) else 0.0
    return brightness_penalty + texture_penalty + transition_penalty + text_penalty


def _compute_adaptive_threshold(pixels, width: int, height: int) -> float:
    """
    计算图像的动态亮度阈值。
    取全图各行的平均亮度的第 ADAPTIVE_BRIGHTNESS_PERCENTILE 百分位。
    """
    step_y = max(1, height // 200)  # 采样 ~200 行
    step_x = max(1, width // 30)    # 每行采 ~30 点
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
    best_score = float("-inf")

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

    if best_score >= 0:
        return best_cut

    # 回退：附近没有完整空白带时，挑选一小段“内容风险”最低的位置。
    best_fallback = target_cut
    best_fallback_score = float("inf")
    window_radius = 2

    for y in range(scan_top + window_radius, max(scan_top + window_radius, scan_bottom - window_radius)):
        score = 0.0
        valid_rows = 0
        for yy in range(y - window_radius, y + window_radius + 1):
            row_score = _row_content_score(pixels, yy, width, adaptive_threshold)
            if row_score != float("inf"):
                score += row_score
                valid_rows += 1

        if not valid_rows:
            continue

        avg_score = score / valid_rows
        avg_score += abs(y - target_cut) * 0.15
        if avg_score < best_fallback_score:
            best_fallback_score = avg_score
            best_fallback = y

    return best_fallback


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

        # ── 计算缩放比例（暂不缩放，供智能切图在原始大图上分析） ────────
        scale_ratio = 1.0
        if target_width and 0 < target_width < orig_w:
            scale_ratio = target_width / orig_w
        scaled_h = int(orig_h * scale_ratio)

        if scaled_h <= max_height:
            if scale_ratio != 1.0:
                new_w = int(orig_w * scale_ratio)
                img = img.resize((new_w, scaled_h), Image.LANCZOS)
                temp_dir = tempfile.gettempdir()
                base_name = Path(image_path).stem
                out_path = os.path.join(temp_dir, f"scaled_{base_name}.png")
                img.save(out_path, format="PNG", optimize=True)
                return [out_path]
            return [image_path]

        # ── 智能切图：在原始图上分析（空白行更宽，更容易检测） ──────────
        orig_pixels = None
        if smart:
            try:
                scan_img = img.convert("RGB") if img.mode != "RGB" else img
                orig_pixels = scan_img.load()
            except Exception:
                orig_pixels = None

        # ── 等比缩放到目标宽度（现在才真正缩放） ────────────────────────
        if scale_ratio != 1.0:
            new_h = int(orig_h * scale_ratio)
            img = img.resize((target_width, new_h), Image.LANCZOS)
            out_w, out_h = target_width, new_h
        else:
            out_w, out_h = orig_w, orig_h

        slice_count = ceil(out_h / max_height)
        slice_paths: List[str] = []
        temp_dir = tempfile.gettempdir()
        base_name = Path(image_path).stem

        current_top = 0
        for i in range(slice_count):
            top = current_top

            if i == slice_count - 1:
                bottom = out_h
            else:
                remaining_slices = slice_count - i
                remaining_height = out_h - top
                slice_height = ceil(remaining_height / remaining_slices)
                bottom = min(out_h, top + slice_height)

                if smart and orig_pixels:
                    # 在原始图像空间搜索空白断点，保留像素级精度
                    orig_slice_h = int(slice_height / scale_ratio) if scale_ratio != 1.0 else slice_height
                    orig_bottom = int(bottom / scale_ratio) if scale_ratio != 1.0 else bottom
                    orig_target = orig_bottom

                    adjusted_orig = _find_smart_cut(orig_pixels, orig_w, orig_h, orig_target, orig_slice_h)
                    adjusted = round(adjusted_orig * scale_ratio)

                    min_bottom = top + max(60, int(slice_height * 0.7))
                    min_bottom = max(min_bottom, out_h - ((remaining_slices - 1) * max_height))
                    max_bottom = min(top + max_height, out_h - ((remaining_slices - 1) * max_height))
                    bottom = max(min_bottom, min(adjusted, max_bottom))

            slice_img = img.crop((0, top, out_w, bottom))

            ext = ".png"
            slice_filename = f"slice_{i}_{base_name}{ext}"
            slice_path = os.path.join(temp_dir, slice_filename)

            if slice_img.mode in ("RGBA", "P"):
                slice_img = slice_img.convert("RGB")
            slice_img.save(slice_path, format="PNG", optimize=True)
            slice_paths.append(slice_path)
            current_top = bottom

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
