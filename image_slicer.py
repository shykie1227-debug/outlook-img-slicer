"""
图像切片器模块
将长图按指定高度切片，支持 JPG/PNG/BMP/WebP/GIF
V4.5 智能切图：通过像素灰度方差 + 亮度综合分析查找安全断点，规避文字区
V4.8.7 Outlook 缝隙根治：切片阶段保证输出 PNG 总高严格 = 原图高，
  配合 html_assembler 的 _even_pixel_up 单组补白底，零累计误差 = 零 1px 缝。
"""
import os
import tempfile
from math import ceil
from typing import List, Tuple
from pathlib import Path
from PIL import Image

from image_safety import check_image_safety, ImageSafetyError


# ── 智能切图常量 ────────────────────────────
SMART_SCAN_RATIO = 0.5        # 扫描窗口 = 切片高度 * 此比率（自适应）
SMART_MIN_SCAN = 80           # 扫描窗口最小 px
SMART_MAX_SCAN = 800          # 扫描窗口最大 px
SMART_MIN_SPACING = 20        # 至少连续 N 行空白才算安全断点
SMART_TEXT_BUFFER = 32        # 切点上下 N px 内不能有文字/线条行（防“贴边切断”）
SMART_MIN_BUFFER_VIOLATIONS = 0  # 缓冲带允许的最大文字行数
BLANK_VARIANCE_THRESHOLD = 6  # 灰度标准差 < 此值视为"行内无变量"（空白/纯色行）
BLANK_TRANSITION_MAX = 0.04   # 过渡比 > 此值说明该行仍有文字/线条（更严）
BLANK_BRIGHTNESS_MIN = 170    # 空白行平均亮度下限（排除深色纯色区）
TEXTURE_VARIANCE_MIN = 8      # 文字行灰度标准差下限（防止漏检小字号/细线条）
TEXTURE_TRANSITION_MIN = 0.08 # 文字行过渡比下限（防止漏检反白文字）

# 动态亮度阈值：低于此亮度视为"非空白"
# 若图像整体偏暗，使用自适应 percentile
ADAPTIVE_BRIGHTNESS_PERCENTILE = 85  # 取全图亮度百分位作为动态阈值


def _even_ceil(n: int) -> int:
    """向上偶数化（与 html_assembler._even_pixel_up 一致）。"""
    if n <= 1:
        return 1
    return n if n % 2 == 0 else n + 1


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

    三重条件（更严）：
    1. 亮度足够高（背景色），排除深色纯色区
    2. 灰度方差足够低（无纹理），排除文字/图片/线条
    3. 过渡比足够低（跳变不频繁），排除稀疏文字

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

    # 条件 3：过渡比必须足够低（排除稀疏文字/虚线）
    if transition_ratio > BLANK_TRANSITION_MAX:
        return False

    return True


def _is_text_like(mean_brightness: float, std_dev: float, transition_ratio: float) -> bool:
    """
    识别文字/线条密集行，用于回退评分和加墙检查。
    同步收紧阈值以避免漏检小字号/细线条/反白文字。
    """
    if mean_brightness <= 30 or mean_brightness >= 254:
        return False
    # 两个条件任一满足即视为文字行（并集而非交集，更严）
    if std_dev >= TEXTURE_VARIANCE_MIN and transition_ratio >= TEXTURE_TRANSITION_MIN:
        return True
    if std_dev >= TEXTURE_VARIANCE_MIN * 1.8 and transition_ratio >= 0.04:
        return True
    return False


def _count_text_rows_in_band(pixels, y_start: int, y_end: int, width: int) -> int:
    """
    统计 [y_start, y_end) 区间内的「文字/线条行」数量。
    用于检查切点上下缓冲带是否靠近文字区（“加墙”逻辑）。
    """
    if y_end <= y_start:
        return 0
    text_rows = 0
    for y in range(y_start, y_end):
        mean, std, samples, trans = _row_stats(pixels, y, width)
        if samples < 5:
            continue
        if _is_text_like(mean, std, trans):
            text_rows += 1
    return text_rows


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

                # ── “加墙”检查：上下缓冲带内不能有文字/线条行 ───────
                upper_start = max(0, cut_pos - SMART_TEXT_BUFFER)
                lower_end = min(height, cut_pos + SMART_TEXT_BUFFER)
                # 跳过空白带本身，只检查上下两端
                text_in_buffer = (
                    _count_text_rows_in_band(pixels, upper_start, y, width)
                    + _count_text_rows_in_band(pixels, y + streak, lower_end, width)
                )
                if text_in_buffer > SMART_MIN_BUFFER_VIOLATIONS:
                    # 上下靠近文字区，该断点不安全，惩罚后继续扫
                    y = yy
                    continue

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

        # “加墙”惩罚：切点上下缓冲带内文字行越多，风险越高
        text_in_buffer = (
            _count_text_rows_in_band(pixels, max(0, y - SMART_TEXT_BUFFER), y, width)
            + _count_text_rows_in_band(pixels, y + 1, min(height, y + SMART_TEXT_BUFFER + 1), width)
        )
        avg_score += text_in_buffer * 25.0

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
                # V4.8.7: 最后一片严格吸收到 out_h，保证 N 片 PNG 物理总高 = 原图高。
                # 配合 html_assembler._even_pixel_up 单组补白底，零累计误差 = 零 1px 缝。
                bottom = out_h
            else:
                remaining_slices = slice_count - i
                remaining_height = out_h - top
                # V4.8.7: 平均切片高度向上偶数化，最后一片不均分而是吸收剩余。
                # 优势：前 N-1 片都是偶数（Word px→pt 无小数），最后一片任意偶奇（容差）。
                # 这与"ceil + 最后吸收"等价，但视觉上更稳。
                base_slice_h = ceil(remaining_height / remaining_slices)
                slice_height = _even_ceil(base_slice_h)
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
                    max_bottom = min(top + max_height, max(top + slice_height, out_h - ((remaining_slices - 1) * max_height)))
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
