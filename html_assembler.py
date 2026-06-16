"""
HTML 组装器模块（V4.8.5 缝隙修复 + V4.7.8 优化版）

V4.8.5 缝隙修复（当前版本）：
  - 取消对单组 PNG 高度的"display_w/total_w → _even_pixel"缩放。
  - 之前 materialize 会把单组 source_row 从 (display_w, actual_h) resize 到
    (display_w, _even_pixel(actual_h * display_w / total_w))，对 833px 这种
    奇数高度会变成 832px，导致声明 height=832 与原始源图差 1px。
  - 3 张普通切片各缩 1px 累计产生肉眼可见的"每片切图衔接处有缝"。
  - 修复：声明 height 严格等于 materialize 输出的 PNG 物理高度，
    materialize 又严格等于源 PNG 物理高度 → Word 引擎 1:1 渲染 → 零缩放 → 零缝。
  - 多组（多 hotspot 横向拼接）仍用统一 row_height，因为各段必须共享同一高度。

V4.7.8 优化点：
  - 优化图片尺寸缓存，减少重复读取
  - 进一步加强 Outlook 缝隙消除（mso-padding-alt, mso-border-alt）
  - 优化多按钮横向拼接宽度分配，避免错位
  - 加强偶数像素约束，防止 px->pt 转换产生小数
  - 统一邮件输出显示宽度为偶数，避免外层表格与内层切片总宽不一致

V1 架构变更：
  - 不再使用 Hotspot Map（图上标注 + 物理切割已在 hotspot_slicer.py 完成）
  - 不再输出 <map> + <area>（Outlook Desktop 不解析，删）
  - 不再输出图外 CTA 文字链接行（"邮件中无任何额外元素"，删）
  - 接受 List[SliceItem]，每项包含 (path, href)：
      * href is None: 普通切片 → <img>
      * href is str:  链接切片 → <a href><img></a>

Outlook 兼容性（第一目标 = Outlook Desktop / Word 引擎）：
  ✓ 仅用 <table> + inline-style
  ✓ <a><img></a> 是最基础 HTML，所有 Outlook 客户端可点
  ✓ width + height HTML 属性（不用 CSS）
  ✓ border="0" + style="display:block;" 消除图片间 1px 间隙
  ✓ cellpadding="0" cellspacing="0" border="0" 消除 cell 间隙
"""
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from html import escape
import os
import uuid
from PIL import Image

# V4.7.8: 图片尺寸缓存，避免重复读取同一文件
_img_dimensions_cache: Dict[str, Tuple[int, int]] = {}

# V4.8.7: materialize 临时文件追踪 — 调用方负责删除
# 每次 materialize_display_slices_strict 调用追加新文件，调用方用 cleanup_temp_slices 删
_materialized_temp_files: List[str] = []


def _track_temp_files(paths: List[str]) -> List[str]:
    """登记本次 materialize 产生的临时文件，返回同一列表便于链式调用。"""
    _materialized_temp_files.extend(paths)
    return paths


def cleanup_temp_slices(paths: List[str]) -> int:
    """
    删除 materialize 产生的临时 PNG 切片，best-effort。

    Args:
        paths: 要删除的文件路径列表

    Returns:
        成功删除的数量
    """
    deleted = 0
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
                deleted += 1
        except OSError:
            pass
    return deleted


def cleanup_all_tracked_temp_slices() -> int:
    """进程退出兜底：删掉本进程所有 materialize 临时文件。"""
    return cleanup_temp_slices(list(_materialized_temp_files))


@dataclass
class SliceItem:
    """
    一张物理切片 + 是否带链接 + sort_key。
    hotspot_slicer.py 的输出直接转成 List[SliceItem]。

    V4.6.7 排序架构：
      - sort_key 是 HTML 输出的唯一排序依据
      - **不依赖** append 顺序、文件名、os.listdir、目录遍历
      - HTML 输出前须 sorted(slices, key=lambda s: s.sort_key)
      - 原切片 sort_key = source_index（整数 1.0, 2.0, 3.0, ...）
      - Hotspot 派生竖条 sort_key = source_index + N*0.001

    V4.6.9：加 original_width 字段，记录**该切片所属原图**的宽度。
    V1 物理切割后，链接竖条只是原图一部分 X 范围。
    HTML 输出时，每段需按 actual_w / original_w 比例分配 display_w，
    否则多段拼起来 = 原图宽 × N倍 ＝ 邮件里**图被拉伸错乱**。
    """
    path: str
    href: Optional[str] = None
    alt_text: str = ""
    sort_key: float = 0.0
    # V4.6.9 修复：原图宽度，用于多段拼接时按比例缩放
    original_width: int = 0


def _get_img_dimensions(img_path: str) -> tuple:
    """
    获取图片实际像素尺寸 (width, height)。
    V4.7.8: 使用缓存，避免重复读取同一文件。
    """
    if img_path in _img_dimensions_cache:
        return _img_dimensions_cache[img_path]
    with Image.open(img_path) as img:
        dims = img.size
        _img_dimensions_cache[img_path] = dims
        return dims


def _clear_dimensions_cache():
    """
    清除图片尺寸缓存（释放内存）。
    每次完整生成 HTML 后调用。
    """
    global _img_dimensions_cache
    _img_dimensions_cache.clear()


def _even_pixel(n: int) -> int:
    """
    V4.7.8: 强制偶数像素。
    Outlook 将 px 转换为 pt 时（如 247px → 185.25pt）会产生小数，
    留 0.25pt 差 = 1px 白线。所有 height/width 必须是偶数。
    最佳：4 的倍数（与字体基线对齐）。
    """
    if n <= 1:
        return max(1, n)
    if n % 2 == 0:
        return n
    return n - 1


def _even_pixel_4x(n: int) -> int:
    """
    V4.8.8: 向上取 4 的倍数。
    Outlook Word 引擎 px→pt 转换: 1px = 0.75pt。
    只有 4 的倍数 px 才能产生整数 pt (4px = 3pt)。
    非 4 倍数的 px 产生 0.5pt 或 0.25pt 小数，
    Word 四舍五入后出现 1px 白线 — 这是 V4.8.2~V4.8.7 缝隙的真正根因。
    833px → 836px (627.0pt 整数) 而非 834px (625.5pt 半点小数)。
    """
    if n <= 1:
        return max(4, ((n + 3) // 4) * 4)
    remainder = n % 4
    if remainder == 0:
        return n
    return n + (4 - remainder)


def _edge_extend_image(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    V4.8.10: 把图片补齐/裁剪到目标尺寸，补齐区域使用边缘像素延展。

    Outlook 发送路径要求 PNG 物理尺寸与 HTML 声明尺寸完全一致。
    旧做法在高度补齐时补白；热点多列路径在宽度向 4px 倍数取整后还会从
    源图越界 crop，Pillow 默认补黑，导致按钮切条后出现竖向黑/白空隙。
    这里统一用边缘像素延展：不缩放原图、不引入白边/黑边，视觉上延续原图。
    """
    target_w = max(1, int(target_w))
    target_h = max(1, int(target_h))
    src = img.convert("RGB") if img.mode != "RGB" else img

    crop_w = min(src.size[0], target_w)
    crop_h = min(src.size[1], target_h)
    base = src.crop((0, 0, crop_w, crop_h))

    if base.size == (target_w, target_h):
        return base.copy()

    out = Image.new("RGB", (target_w, target_h))
    out.paste(base, (0, 0))

    if crop_w < target_w:
        right_edge = base.crop((crop_w - 1, 0, crop_w, crop_h))
        for x in range(crop_w, target_w):
            out.paste(right_edge, (x, 0))

    if crop_h < target_h:
        bottom_edge = out.crop((0, crop_h - 1, target_w, crop_h))
        for y in range(crop_h, target_h):
            out.paste(bottom_edge, (0, y))

    return out


def _even_pixel_up(n: int) -> int:
    """
    V4.8.5: 向上偶数化（向下兼容到下一个偶数）。
    用于多组场景（统一 row_height 仍走此路径）。
    ⚠️ V4.8.8: 单组场景已改用 _even_pixel_4x，因为 2 倍数但非 4 倍数
    的 px 值（如 834）在 Outlook px→pt 转换中产生 0.5pt 小数 → 白线。
    """
    if n <= 1:
        return max(1, n)
    if n % 2 == 0:
        return n
    return n + 1


def _normalize_display_width(display_w: int) -> int:
    """
    统一邮件显示宽度。
    V4.8.8: 强制 4 的倍数。Outlook px→pt 转换 (1px=0.75pt)，
    只有 4 的倍数产生整数 pt，消除 1px 白线。
    """
    try:
        value = int(display_w)
    except (TypeError, ValueError):
        value = 648  # 默认 648 = 4 的倍数 = 486pt
    return _even_pixel_4x(max(1, value))


def _distribute_units(raw: List[float], total_units: int) -> List[int]:
    """按最大余数法把 total_units 分配给每段，每段至少 1 个单位。"""
    if not raw:
        return []
    units = [max(1, int(v)) for v in raw]
    remainder = total_units - sum(units)
    fractions = sorted(
        range(len(raw)),
        key=lambda i: raw[i] - int(raw[i]),
        reverse=(remainder > 0),
    )
    idx = 0
    while remainder != 0 and fractions:
        target = fractions[idx % len(fractions)]
        if remainder > 0:
            units[target] += 1
            remainder -= 1
        elif units[target] > 1:
            units[target] -= 1
            remainder += 1
        idx += 1
    return units


def _build_cell(slice_path: str, cid_or_src: str, display_w: int, href: Optional[str] = None,
              alt: str = "", original_width: int = 0, is_base64: bool = False,
              forced_display_w: Optional[int] = None,
              forced_display_h: Optional[int] = None) -> str:
    """
    生成一张切片的 <td>...</td>（V4.7.8 缝隙消除+错位修复）。

    V4.7.8 优化点：
      - 进一步加强 Outlook 缝隙消除（mso-line-height-rule 强制）
      - 所有尺寸严格偶数化
      - 添加 mso-table-lspace/mso-table-rspace 相关属性

    拆 _build_image_row 的原因：
      之前每段占一整 <tr> → 纵向堆叠 → V1 物理切割产物重叠成
      “碎片化”视觉。现在改为同 source_index 的多段拼成一行 <tr>，
      每段 1 个 <td> 横向并排，恢反原图。

    Args:
        cid_or_src: 若是 base64 模式（复制到剪贴板）则传 data:xxx；CID 模式传 cid:xxx
        is_base64: True = generate_plain_html 路径，False = assemble_html 路径
    """
    try:
        actual_w, actual_h = _get_img_dimensions(slice_path)
    except Exception:
        actual_w, actual_h = 650, 650

    display_w = _normalize_display_width(display_w)
    if forced_display_w is not None:
        seg_display_w = _even_pixel_4x(max(1, int(forced_display_w)))
    elif original_width > 0 and actual_w > 0:
        ratio = actual_w / original_width
        seg_display_w = _even_pixel_4x(round(display_w * ratio))
    else:
        seg_display_w = _even_pixel_4x(display_w)
    # V4.8.8: forced_display_h 已由 _compute_group_height 算好（4 的倍数），
    # 直接用，不再二次处理。
    if forced_display_h is not None:
        seg_display_h = max(1, int(forced_display_h))
    else:
        raw_h = round(actual_h * seg_display_w / actual_w) if actual_w else 650
        seg_display_h = _even_pixel_4x(raw_h)

    if not alt:
        alt = Path(slice_path).name
    safe_alt = escape(alt, quote=True)

    # base64 模式 vs CID 模式
    if is_base64:
        import base64
        with open(slice_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        ext = Path(slice_path).suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        src = f"data:{mime};base64,{b64}"
    else:
        src = cid_or_src
    safe_src = escape(src, quote=True)

    img_tag = (
        f'<img src="{safe_src}" '
        f'width="{seg_display_w}" '
        f'height="{seg_display_h}" '
        f'alt="{safe_alt}" '
        f'border="0" hspace="0" vspace="0" '
        f'style="width: {seg_display_w}px; height: {seg_display_h}px; '
        f'border: 0; border-collapse: collapse; border-spacing: 0; '
        f'display: block; outline: none; text-decoration: none; '
        f'vertical-align: top; margin: 0; padding: 0; '
        f'line-height: 0; font-size: 0; '
        f'-ms-interpolation-mode: bicubic;" />'
    )

    if href:
        safe_href = escape(href, quote=True)
        inner = (
            f'<a href="{safe_href}" target="_blank" '
            f'style="display: block; width: {seg_display_w}px; height: {seg_display_h}px; '
            f'text-decoration: none; outline: none; border: 0; border-collapse: collapse; '
            f'mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px; '
            f'line-height: 0; font-size: 0;">'
            f'{img_tag}'
            f'</a>'
        )
    else:
        inner = img_tag

    return (
        f'<td align="left" valign="top" width="{seg_display_w}" height="{seg_display_h}" style="'
        f'width: {seg_display_w}px; height: {seg_display_h}px; '
        f'padding: 0; margin: 0; border: 0; border-collapse: collapse; border-spacing: 0; '
        f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
        f'vertical-align: top; mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px; '
        f'mso-text-raise: 0;'
        f'">'
        f'{inner}'
        f'</td>\n'
    )


def _build_image_row(slice_path: str, cid: str, display_w: int, href: Optional[str] = None, alt: str = "",
                    original_width: int = 0) -> str:
    """
    兼容旧 API：返回 <tr><td>...</td></tr>。
    V4.6.9 后推荐使用 _build_cell + 手工拼 <tr>（见 assemble_html）。
    """
    return (
        f'<tr>\n'
        f'{_build_cell(slice_path, cid, display_w, href, alt, original_width)}'
        f'</tr>\n'
    )


def _group_by_source(slices: List[SliceItem]) -> List[List[SliceItem]]:
    """
    按 sort_key 整数部分（即 source_index）分组，同一原图的所有段（含 hotspot 派生竖条）为一组。
    组内按 sort_key 小数部分升序，组间按 source_index 升序。

    V4.6.9 重构：使用纯 sort_key 推导，不依赖 sort_key 外部存储。
    """
    sorted_slices = sorted(slices, key=lambda s: s.sort_key)
    groups: List[List[SliceItem]] = []
    current_group: List[SliceItem] = []
    current_source: int = None
    for s in sorted_slices:
        src_idx = int(s.sort_key)  # 1.001 → 1
        if current_source is None or src_idx != current_source:
            if current_group:
                groups.append(current_group)
            current_group = [s]
            current_source = src_idx
        else:
            current_group.append(s)
    if current_group:
        groups.append(current_group)
    return groups


def _allocate_group_widths(group: List[SliceItem], display_w: int) -> Dict[str, int]:
    """
    V4.7.8 优化版：为同一原图的横向分段分配显示宽度，保证总和严格等于 display_w。

    Outlook 的 Word 引擎对表格宽度非常敏感。逐段 round() 可能让一行总宽
    变成 display_w±1px，实际发送时容易被重排或换行，表现为标注切片错位。

    V4.7.8 优化：
      - 首先确保 display_w 是偶数
      - 偶数化每一段宽度后，精确调整最后一段保持总和
    """
    if not group:
        return {}
    if len(group) == 1:
        return {group[0].path: _normalize_display_width(display_w)}

    # V4.7.8: 先确保目标显示宽度是偶数
    target_w = _normalize_display_width(display_w)

    dims: List[Tuple[SliceItem, int]] = []
    for s in group:
        try:
            actual_w, _ = _get_img_dimensions(s.path)
        except Exception:
            actual_w = 0
        dims.append((s, actual_w))

    total_actual_w = sum(w for _, w in dims if w > 0)
    if total_actual_w <= 0:
        weights = [1.0] * len(group)
    else:
        weights = [max(1, w) / total_actual_w for _, w in dims]

    # V4.8.8: 优先按 4px 单位分配，保证每段、总宽都是 4 的倍数，
    # 避免 Outlook px→pt 小数白线。
    # 如果段数极端多到 4px 都分不下，退回 2px 单位，最后退回 1px。
    if target_w // 4 >= len(group):
        total_units = target_w // 4
        raw_units = [weight * total_units for weight in weights]
        even_widths = [u * 4 for u in _distribute_units(raw_units, total_units)]
    elif target_w // 2 >= len(group):
        total_units = target_w // 2
        raw_units = [weight * total_units for weight in weights]
        even_widths = [u * 2 for u in _distribute_units(raw_units, total_units)]
    else:
        raw_pixels = [weight * target_w for weight in weights]
        even_widths = _distribute_units(raw_pixels, target_w)

    diff = target_w - sum(even_widths)
    if diff and even_widths:
        even_widths[-1] = max(1, even_widths[-1] + diff)

    return {s.path: w for (s, _), w in zip(dims, even_widths)}


def _compute_group_height(group: List[SliceItem], display_w: int) -> int:
    """
    同一原图的横向分段必须使用同一个显示高度，避免 Outlook 中上下错位。

    V4.7.7: 输出强制偶数（Outlook px→pt 转换无小数 → 消除 1px 白线）。
    V4.8.5: 单组（len(group)==1）改为向上偶数化 actual_h。
    V4.8.8: 单组改用 _even_pixel_4x（4 的倍数），因为 2 的倍数中有一半
      不是 4 的倍数，产生 0.5pt 小数 → Word 四舍五入 → 白线。
      例：833px → _even_pixel_up=834 (625.5pt ❌) → _even_pixel_4x=836 (627.0pt ✅)
      多组仍走统一 row_height 计算（多段必须共享 row_h），并对齐 4 的倍数。
    """
    display_w = _normalize_display_width(display_w)

    # V4.8.8: 单组走"4 的倍数"路径
    if len(group) == 1:
        try:
            _, actual_h = _get_img_dimensions(group[0].path)
        except Exception:
            return _even_pixel_4x(display_w)
        if actual_h > 0:
            return _even_pixel_4x(actual_h)
        return _even_pixel_4x(display_w)

    total_w = 0
    row_h = 0
    for s in group:
        try:
            actual_w, actual_h = _get_img_dimensions(s.path)
        except Exception:
            continue
        if actual_w > 0:
            total_w += actual_w
            row_h = max(row_h, actual_h)
    if total_w <= 0 or row_h <= 0:
        return _even_pixel_4x(display_w)
    # V4.8.8: 多组也改用 4 的倍数
    return _even_pixel_4x(max(1, round(row_h * display_w / total_w)))


def _build_group_row(group: List[SliceItem], display_w: int, cid_counter: int,
                     is_base64: bool = False) -> Tuple[str, int]:
    """
    为一张原始切片生成完整外层行。

    关键：外层 table 永远只有 1 列；每张原图自己的横向分段放进独立内层 table。
    Outlook/Word 会把同一张 table 的列当作全局列网格，如果直接在外层混用
    “多列 hotspot 行”和“单列普通行”，普通行会被前面多列宽度污染，表现为
    左右错位、显示不全或局部重叠。
    """
    display_w = _normalize_display_width(display_w)
    allocated_widths = _allocate_group_widths(group, display_w)
    row_height = _compute_group_height(group, display_w)

    # V4.8.3: 普通纵向切片不要再套一层内层 table。
    # Outlook/Word 对嵌套表格的行高重算很激进，单图行使用扁平结构更稳定。
    if len(group) == 1:
        s = group[0]
        if is_base64:
            cid_or_src = ""
        else:
            cid_counter += 1
            cid_or_src = f"cid:slice_{cid_counter:03d}"
        cell = _build_cell(
            s.path, cid_or_src, display_w, s.href, s.alt_text,
            s.original_width, is_base64=is_base64,
            forced_display_w=allocated_widths.get(s.path),
            forced_display_h=row_height,
        )
        row = (
            f'<tr height="{row_height}" style="height: {row_height}px; '
            f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
            f'mso-margin-top-alt: 0; mso-margin-bottom-alt: 0; border: 0;" '
            f'valign="top" align="left">\n'
            f'{cell}'
            f'</tr>\n'
        )
        return row, cid_counter

    cells = ""
    for s in group:
        if is_base64:
            cid_or_src = ""
        else:
            cid_counter += 1
            cid_or_src = f"cid:slice_{cid_counter:03d}"
        cells += _build_cell(
            s.path, cid_or_src, display_w, s.href, s.alt_text,
            s.original_width, is_base64=is_base64,
            forced_display_w=allocated_widths.get(s.path),
            forced_display_h=row_height,
        )

    inner_table = (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" '
        f'width="{display_w}" '
        f'style="width: {display_w}px; border: 0; border-collapse: collapse; border-spacing: 0; '
        f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
        f'mso-table-lspace: 0pt; mso-table-rspace: 0pt; '
        f'mso-table-bspace: 0pt; mso-table-tspace: 0pt; '
        f'mso-table-bspace-snap: 1000; mso-table-tspace-snap: 1000; '
        f'mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px; '
        f'table-layout: fixed;">\n'
        f'<tr height="{row_height}" style="height: {row_height}px; '
        f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
        f'mso-margin-top-alt: 0; mso-margin-bottom-alt: 0; border: 0;" valign="top" align="left">\n'
        f'{cells}'
        f'</tr>\n'
        f'</table>'
    )
    row = (
        f'<tr height="{row_height}" style="height: {row_height}px; '
        f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
        f'mso-margin-top-alt: 0; mso-margin-bottom-alt: 0; border: 0;" valign="top" align="left">\n'
        f'<td align="center" valign="top" width="{display_w}" height="{row_height}" style="'
        f'width: {display_w}px; height: {row_height}px; padding: 0; margin: 0; '
        f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
        f'border: 0; border-collapse: collapse; border-spacing: 0; vertical-align: top; '
        f'mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px;">'
        f'{inner_table}'
        f'</td>\n'
        f'</tr>\n'
    )
    return row, cid_counter


def materialize_display_slices(slices: List[SliceItem], display_w: int = 650) -> List[SliceItem]:
    """
    生成一组“最终显示尺寸”的临时切片。

    Outlook/Word 对多个相邻图片段分别缩放时，边缘插值容易产生 1px 竖缝或重叠。
    这里提前把每段 resize 到 HTML 中声明的最终宽高，让 Outlook 只按 1:1 显示，
    不再参与缩放计算。
    """
    if not slices:
        return []

    groups = _group_by_source(slices)
    prepared: List[SliceItem] = []
    out_dir = Path(slices[0].path).parent
    batch = uuid.uuid4().hex[:8]
    counter = 0

    # V4.8.8: 偶数化 display_w 对齐 4 的倍数，保证 resize 后尺寸 px→pt 无小数
    display_w_even = _normalize_display_width(display_w)

    for group in groups:
        allocated_widths = _allocate_group_widths(group, display_w_even)
        row_height = _compute_group_height(group, display_w_even)
        try:
            source_parts = []
            total_w = 0
            max_h = 0
            for s in group:
                with Image.open(s.path) as img:
                    part = img.convert("RGB")
                    source_parts.append((s, part.copy()))
                    total_w += part.width
                    max_h = max(max_h, part.height)
            if total_w <= 0 or max_h <= 0:
                raise ValueError("invalid image size")

            source_row = Image.new("RGB", (total_w, max_h))
            x = 0
            for _, part in source_parts:
                source_row.paste(part, (x, 0))
                x += part.width

            # V4.8.10: 当 source_row 宽/高需要补齐到 4px 倍数时，不能补白边/黑边。
            # 用户目标是 Outlook 里看起来像一整张长图；白底 padding 会在非白背景/渐变/图片内容
            # 的切片底部形成肉眼可见割裂；热点多列路径宽度 650→652 时，越界 crop 会补黑。
            # 正确做法是延展边缘像素，既不缩放原图，又让补齐区域视觉上延续原图边缘。
            target_total_w = sum(
                _even_pixel_4x(int(allocated_widths.get(s.path, display_w_even)))
                for s, _ in source_parts
            )
            source_row = _edge_extend_image(source_row, target_total_w, row_height)

            crop_x = 0
            for s, _ in source_parts:
                counter += 1
                # V4.8.8: target_w 对齐 4 的倍数（与 HTML width 声明对齐）
                target_w = _even_pixel_4x(int(allocated_widths.get(s.path, display_w_even)))
                target_path = out_dir / f"mail_{batch}_{counter:03d}.png"
                part = source_row.crop((crop_x, 0, crop_x + target_w, row_height))
                part.save(target_path, "PNG")
                crop_x += target_w
                prepared.append(SliceItem(
                    path=str(target_path),
                    href=s.href,
                    alt_text=s.alt_text,
                    sort_key=s.sort_key,
                    original_width=display_w_even,
                ))
        except Exception:
            for s in group:
                prepared.append(s)

    return prepared


def materialize_display_slices_strict(slices: List[SliceItem], display_w: int = 650) -> List[SliceItem]:
    """
    生成最终显示尺寸切片，并拒绝 materialize_display_slices 的静默降级结果。

    Outlook 发送路径依赖实际 PNG 尺寸与 HTML width/height 完全一致。若预渲染失败后
    返回原图，Word 引擎会重新缩放图片，容易重新出现 1px 缝隙。

    V4.8.7：登记所有新建临时文件，调用方可用 cleanup_temp_slices 删除。
    """
    if not slices:
        return []

    original_paths = {s.path for s in slices}
    prepared = materialize_display_slices(slices, display_w)
    prepared_paths = [s.path for s in prepared]
    fallback_paths = [p for p in prepared_paths if p in original_paths]
    missing_paths = [p for p in prepared_paths if not Path(p).exists()]

    if fallback_paths or missing_paths or len(prepared) != len(slices):
        raise RuntimeError(
            "最终邮件切片预渲染失败，已阻止发送以避免 Outlook 中出现图片缝隙。"
            "请重新切图后再试。"
        )

    # V4.8.7: 跟踪新建的临时文件，便于调用方清理
    new_files = [p for p in prepared_paths if p not in original_paths]
    _track_temp_files(new_files)

    return prepared


def assemble_html(slices: List[SliceItem], display_w: int = 650) -> str:
    """
    生成适用于 Outlook 的 HTML 邮件正文（CID 内联嵌入版）。

    V4.6.9 重构：同 source_index 的多段拼成 1 个 <tr>（横向拼接），
    不同 source_index 之间用独立 <tr>（纵向堆叠）。这样:
      1. 单张原图的所有段（包括 hotspot 派生竖条）拼成 1 行 → 恢反原图视觉
      2. 多张原图（智能切图切了 N 段 Y）→ N 行 × K 列

    V4.7.8: 最后清理图片尺寸缓存
    """
    display_w = _normalize_display_width(display_w)
    try:
        sorted_slices = sorted(slices, key=lambda s: s.sort_key)
        groups = _group_by_source(sorted_slices)
        rows = ""
        cid_counter = 0
        for group in groups:
            row, cid_counter = _build_group_row(group, display_w, cid_counter, is_base64=False)
            rows += row

        return (
            f'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
            f'"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office">\n'
            f'<head>\n'
            f'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f'<title>长图邮件</title>\n'
            f'</head>\n'
            f'<body style="margin: 0; padding: 0; background-color: #ffffff; '
            f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
            f'Margin: 0;">\n'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            f'align="center" '
            f'width="{display_w}" '
            f'style="width: {display_w}px; border: 0; border-collapse: collapse; border-spacing: 0; '
            f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
            f'mso-table-lspace: 0pt; mso-table-rspace: 0pt; '
            f'mso-table-bspace: 0pt; mso-table-tspace: 0pt; '
            f'mso-table-bspace-snap: 1000; mso-table-tspace-snap: 1000; '
            f'table-layout: fixed;">\n'
            f'{rows}'
            f'</table>\n'
            f'</body>\n'
            f'</html>'
        )
    finally:
        # V4.7.8: 清理缓存，释放内存
        _clear_dimensions_cache()


def get_cid_map(slices: List[SliceItem]) -> Dict[int, str]:
    """返回 {index: cid} 映射，给 outlook_sender.py 用。"""
    sorted_slices = sorted(slices, key=lambda s: s.sort_key)
    return {i: f"slice_{i + 1:03d}" for i in range(len(sorted_slices))}


def generate_plain_html(slices: List[SliceItem], display_w: int = 650) -> str:
    """
    生成纯内联 base64 的 HTML，供复制到剪贴板使用（不进 Outlook，直接贴到 Gmail / 网页邮箱）。

    V4.6.9 重构：同 assemble_html 一样按 source_index 分组横向拼接。
    V4.7.8: 最后清理图片尺寸缓存。
    V4.8.1: 入口先 materialize_display_slices，
    保证实际 PNG 高度与 HTML 声明 height 严格一致，
    避免 1px 溢出导致的 Outlook 纵向缝（根因 H3：generate_plain_html
    独立调用时跳过 materialize，row_height 偶数化后的高度与实际 PNG 不一致）。
    V4.8.1.1: materialize 内部静默降级会导致本修复失效，入口加 guard
    确保 materialize 实际产生了新文件（路径以 mail_ 开头）。
    """
    display_w = _normalize_display_width(display_w)
    try:
        # V4.8.2：复制路径也使用严格预渲染，和发送路径保持同一套防缝隙入口。
        slices = materialize_display_slices_strict(slices, display_w)
        sorted_slices = sorted(slices, key=lambda s: s.sort_key)
        groups = _group_by_source(sorted_slices)
        rows = ""
        cid_counter = 0
        for group in groups:
            row, cid_counter = _build_group_row(group, display_w, cid_counter, is_base64=True)
            rows += row
        return (
            f'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
            f'"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml">\n'
            f'<head>\n'
            f'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
            f'<title>长图邮件</title>\n'
            f'</head>\n'
            f'<body style="margin: 0; padding: 0; background-color: #ffffff; '
            f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
            f'Margin: 0;">\n'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
            f'align="center" '
            f'width="{display_w}" '
            f'style="width: {display_w}px; border: 0; border-collapse: collapse; border-spacing: 0; '
            f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
            f'mso-table-lspace: 0pt; mso-table-rspace: 0pt; '
            f'mso-table-bspace: 0pt; mso-table-tspace: 0pt; '
            f'mso-table-bspace-snap: 1000; mso-table-tspace-snap: 1000; '
            f'table-layout: fixed;">\n'
            f'{rows}'
            f'</table>\n'
            f'</body>\n'
            f'</html>'
        )
    finally:
        # V4.7.8: 清理缓存，释放内存
        _clear_dimensions_cache()
