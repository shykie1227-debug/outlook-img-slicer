"""
HTML 组装器模块（V4.6.6 V1 重写）

V1 架构变更：
  - 不再使用 HotspotMap（图上标注 + 物理切割已在 hotspot_slicer.py 完成）
  - 不再输出 <map> + <area>（Outlook 桌面端不解析，删）
  - 不再输出图外 CTA 文字链接行（"邮件中无任何额外元素"，删）
  - 接受 List[SliceItem]，每项包含 (path, href)：
      * href is None: 普通切片 → <img>
      * href is str:  链接切片 → <a href><img></a>

Outlook 兼容性（第一目标 = Outlook Desktop / Word 引擎）：
  ✅ 仅用 <table> + inline-style
  ✅ <a><img></a> 是最基础 HTML，所有 Outlook 客户端可点
  ✅ width + height HTML 属性（不用 CSS）
  ✅ border="0" + style="display:block;" 消除图片间 1px 间隙
  ✅ cellpadding="0" cellspacing="0" border="0" 消除 cell 间隙
"""
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from html import escape
import uuid
from PIL import Image


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
    """获取图片实际像素尺寸 (width, height)"""
    with Image.open(img_path) as img:
        return img.size


def _even_pixel(n: int) -> int:
    """
    V4.7.7: 强制偶数像素。
    Outlook 将 px 转换为 pt 时（如 247px → 185.25pt）会产生小数，
    留 0.25pt 差 = 1px 白线。所有 height/width 必须是偶数。
    最佳：4 的倍数（与字体基线对齐）。
    """
    if n <= 1:
        return max(1, n)
    if n % 2 == 0:
        return n
    return n - 1


def _build_cell(slice_path: str, cid_or_src: str, display_w: int, href: Optional[str] = None,
              alt: str = "", original_width: int = 0, is_base64: bool = False,
              forced_display_w: Optional[int] = None,
              forced_display_h: Optional[int] = None) -> str:
    """
    生成一张切片的 <td>...</td>（V4.6.9 修复纵向→横向拼接）。

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

    if forced_display_w is not None:
        seg_display_w = _even_pixel(max(1, int(forced_display_w)))
    elif original_width > 0 and actual_w > 0:
        ratio = actual_w / original_width
        seg_display_w = _even_pixel(round(display_w * ratio))
    else:
        seg_display_w = _even_pixel(display_w)
    if forced_display_h is not None:
        seg_display_h = _even_pixel(max(1, int(forced_display_h)))
    else:
        raw_h = round(actual_h * seg_display_w / actual_w) if actual_w else 650
        seg_display_h = _even_pixel(raw_h)

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
        f'border: 0; display: block; outline: none; text-decoration: none; '
        f'vertical-align: top; margin: 0; padding: 0; '
        f'-ms-interpolation-mode: bicubic;" />'
    )

    if href:
        safe_href = escape(href, quote=True)
        inner = (
            f'<a href="{safe_href}" target="_blank" '
            f'style="display: block; width: {seg_display_w}px; height: {seg_display_h}px; '
            f'text-decoration: none; outline: none; border: 0; '
            f'mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px;">'
            f'{img_tag}'
            f'</a>'
        )
    else:
        inner = img_tag

    return (
        f'<td align="left" valign="top" width="{seg_display_w}" height="{seg_display_h}" style="'
        f'width: {seg_display_w}px; height: {seg_display_h}px; '
        f'padding: 0; margin: 0; '
        f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
        f'border: 0; vertical-align: top;'
        f'mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px;"'
        f'>'
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
    为同一原图的横向分段分配显示宽度，保证总和严格等于 display_w。

    Outlook 的 Word 引擎对表格宽度非常敏感。逐段 round() 可能让一行总宽
    变成 display_w±1px，实际发送时容易被重排或换行，表现为标注切片错位。
    """
    if not group:
        return {}
    if len(group) == 1:
        return {group[0].path: display_w}

    dims: List[Tuple[SliceItem, int]] = []
    for s in group:
        try:
            actual_w, _ = _get_img_dimensions(s.path)
        except Exception:
            actual_w = 0
        dims.append((s, actual_w))

    total_actual_w = sum(w for _, w in dims if w > 0)
    if total_actual_w <= 0:
        base = max(1, display_w // len(group))
        widths = [base] * len(group)
        widths[-1] += display_w - sum(widths)
        return {s.path: max(1, w) for (s, _), w in zip(dims, widths)}

    raw = [(w / total_actual_w) * display_w for _, w in dims]
    widths = [max(1, int(v)) for v in raw]
    remainder = display_w - sum(widths)

    fractions = sorted(
        range(len(raw)),
        key=lambda i: raw[i] - int(raw[i]),
        reverse=(remainder > 0),
    )
    idx = 0
    while remainder != 0 and fractions:
        target = fractions[idx % len(fractions)]
        if remainder > 0:
            widths[target] += 1
            remainder -= 1
        elif widths[target] > 1:
            widths[target] -= 1
            remainder += 1
        idx += 1

    # V4.7.7: 偶数化所有 width，最后一个补齐差保持总和 = display_w
    even_widths = [w if w % 2 == 0 else (w - 1 if w > 1 else w) for w in widths]
    diff = sum(widths) - sum(even_widths)
    if even_widths and diff != 0:
        even_widths[-1] = max(1, even_widths[-1] + diff)
    return {s.path: w for (s, _), w in zip(dims, even_widths)}


def _compute_group_height(group: List[SliceItem], display_w: int) -> int:
    """
    同一原图的横向分段必须使用同一个显示高度，避免 Outlook 中上下错位。
    V4.7.7: 输出强制偶数（Outlook px→pt 转换无小数 → 消除 1px 白线）。
    """
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
        return _even_pixel(display_w)
    return _even_pixel(max(1, round(row_h * display_w / total_w)))


def _build_group_row(group: List[SliceItem], display_w: int, cid_counter: int,
                     is_base64: bool = False) -> Tuple[str, int]:
    """
    为一张原始切片生成完整外层行。

    关键：外层 table 永远只有 1 列；每张原图自己的横向分段放进独立内层 table。
    Outlook/Word 会把同一张 table 的列当作全局列网格，如果直接在外层混用
    “多列 hotspot 行”和“单列普通行”，普通行会被前面多列宽度污染，表现为
    左右错位、显示不全或局部重叠。
    """
    allocated_widths = _allocate_group_widths(group, display_w)
    row_height = _compute_group_height(group, display_w)
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
        f'style="width: {display_w}px; border-collapse: collapse; border-spacing: 0; '
        f'mso-table-lspace: 0pt; mso-table-rspace: 0pt; '
        f'mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px;">\n'
        f'<tr height="{row_height}" style="height: {row_height}px; '
        f'font-size: 0; line-height: 0; mso-line-height-rule: exactly;">\n'
        f'{cells}'
        f'</tr>\n'
        f'</table>'
    )
    row = (
        f'<tr>\n'
        f'<td align="center" valign="top" width="{display_w}" style="'
        f'width: {display_w}px; padding: 0; margin: 0; '
        f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
        f'border: 0; vertical-align: top;">'
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

    # V4.7.7: 偶数化 display_w，保证 resize 后源图尺寸偶数
    display_w_even = _even_pixel(display_w)

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

            source_row = Image.new("RGB", (total_w, max_h), (255, 255, 255))
            x = 0
            for _, part in source_parts:
                source_row.paste(part, (x, 0))
                x += part.width

            if source_row.size != (display_w_even, row_height):
                source_row = source_row.resize((display_w_even, row_height), Image.Resampling.LANCZOS)

            crop_x = 0
            for s, _ in source_parts:
                counter += 1
                # V4.7.7: target_w 强制偶数（与 HTML width 声明对齐）
                target_w = _even_pixel(int(allocated_widths.get(s.path, display_w_even)))
                target_path = out_dir / f"mail_{batch}_{counter:03d}.png"
                part = source_row.crop((crop_x, 0, crop_x + target_w, row_height))
                part.save(target_path, "PNG")
                crop_x += target_w
                prepared.append(SliceItem(
                    path=str(target_path),
                    href=s.href,
                    alt_text=s.alt_text,
                    sort_key=s.sort_key,
                    original_width=display_w,
                ))
        except Exception:
            for s in group:
                prepared.append(s)

    return prepared


def assemble_html(slices: List[SliceItem], display_w: int = 650) -> str:
    """
    生成适用于 Outlook 的 HTML 邮件正文（CID 内联嵌入版）。

    V4.6.9 重构：同 source_index 的多段拼成 1 个 <tr>（横向拼接），
    不同 source_index 之间用独立 <tr>（纵向堆叠）。这样:
      1. 单张原图的所有段（包括 hotspot 派生竖条）拼成 1 行 → 恢反原图视觉
      2. 多张原图（智能切图切了 N 段 Y）→ N 行 × K 列
    """
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
        f'<body style="margin: 0; padding: 0; background-color: #ffffff;">\n'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'align="center" '
        f'width="{display_w}" '
        f'style="width: {display_w}px; border-collapse: collapse; border-spacing: 0; '
        f'mso-table-lspace: 0pt; mso-table-rspace: 0pt;">\n'
        f'{rows}'
        f'</table>\n'
        f'</body>\n'
        f'</html>'
    )


def get_cid_map(slices: List[SliceItem]) -> Dict[int, str]:
    """返回 {index: cid} 映射，给 outlook_sender.py 用。"""
    sorted_slices = sorted(slices, key=lambda s: s.sort_key)
    return {i: f"slice_{i + 1:03d}" for i in range(len(sorted_slices))}


def generate_plain_html(slices: List[SliceItem], display_w: int = 650) -> str:
    """
    生成纯内联 base64 的 HTML，供复制到剪贴板使用（不进 Outlook，直接贴到 Gmail / 网页邮箱）。

    V4.6.9 重构：同 assemble_html 一样按 source_index 分组横向拼接。
    """
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
        f'<body style="margin: 0; padding: 0; background-color: #ffffff;">\n'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        f'align="center" '
        f'width="{display_w}" '
        f'style="width: {display_w}px; border-collapse: collapse; border-spacing: 0;">\n'
        f'{rows}'
        f'</table>\n'
        f'</body>\n'
        f'</html>'
    )
