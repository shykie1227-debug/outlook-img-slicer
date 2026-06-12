"""
图片安全限制模块
防止超大图、内存溢出、Pillow 卡死
"""
import os
from PIL import Image, UnidentifiedImageError
from pathlib import Path

# 安全限制常量
MAX_IMAGE_WIDTH = 30000
MAX_IMAGE_HEIGHT = 30000
MAX_PIXELS = 250_000_000
MAX_FILE_SIZE_MB = 500


class ImageSafetyError(Exception):
    """图片安全检查未通过"""
    pass


def check_image_safety(path: str) -> None:
    """
    对图片文件进行安全检查，不通过则抛出 ImageSafetyError。
    检查项：文件大小、像素尺寸、总像素数。

    V4.8.7: 全文包 try/except，文件不存在/损坏/无权限时抛 ImageSafetyError
    （原版抛 FileNotFoundError 直接到 UI，UI 看不懂）
    """
    try:
        file_size_mb = Path(path).stat().st_size / 1024 / 1024
    except OSError as e:
        raise ImageSafetyError(f"无法访问文件: {e}") from e

    if file_size_mb > MAX_FILE_SIZE_MB:
        raise ImageSafetyError(
            f"文件过大（{file_size_mb:.1f}MB），超过上限 {MAX_FILE_SIZE_MB}MB"
        )

    try:
        with Image.open(path) as img:
            w, h = img.size
    except (UnidentifiedImageError, OSError) as e:
        raise ImageSafetyError(f"无法识别图片格式或文件已损坏: {e}") from e

    if w > MAX_IMAGE_WIDTH:
        raise ImageSafetyError(f"图片宽度 {w}px 超过上限 {MAX_IMAGE_WIDTH}px")
    if h > MAX_IMAGE_HEIGHT:
        raise ImageSafetyError(f"图片高度 {h}px 超过上限 {MAX_IMAGE_HEIGHT}px")

    total_pixels = w * h
    if total_pixels > MAX_PIXELS:
        raise ImageSafetyError(
            f"图片总像素 {total_pixels:,} 超过上限 {MAX_PIXELS:,}"
        )


def estimate_email_size_mb(slice_paths) -> float:
    """
    估算邮件总大小（切片大小 + HTML 开销）。
    HTML 开销按每张切片约 1KB 估算。

    V4.8.7: 文件不存在/无权限时跳过该项，不让单条坏路径炸掉整次估算
    """
    if not slice_paths:
        return 0.0
    total_bytes = 0
    for p in slice_paths:
        try:
            total_bytes += Path(p).stat().st_size
        except OSError:
            # 文件不存在/无权限，单条跳过
            continue
    # HTML overhead: ~1KB per slice + 2KB base
    html_overhead_bytes = (len(slice_paths) + 2) * 1024
    return round((total_bytes + html_overhead_bytes) / 1024 / 1024, 1)
