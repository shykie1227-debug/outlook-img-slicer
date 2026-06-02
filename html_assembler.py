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


def _build_cell(slice_path: str, cid_or_src: str, display_w: int, href: Optional[str] = None,
              alt: str = "", original_width: int = 0, is_base64: bool = False) -> str:
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

    if original_width > 0 and actual_w > 0:
        ratio = actual_w / original_width
        seg_display_w = round(display_w * ratio)
    else:
        seg_display_w = display_w
    seg_display_h = round(actual_h * seg_display_w / actual_w) if actual_w else 650

    if not alt:
        alt = Path(slice_path).name

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

    img_tag = (
        f'<img src="{src}" '
        f'width="{seg_display_w}" '
        f'height="{seg_display_h}" '
        f'alt="{alt}" '
        f'border="0" '
        f'style="border: 0; display: block; outline: none; text-decoration: none;" />'
    )

    if href:
        inner = (
            f'<a href="{href}" target="_blank" '
            f'style="display: block; text-decoration: none; outline: none;">'
            f'{img_tag}'
            f'</a>'
        )
    else:
        inner = img_tag

    return (
        f'<td align="left" valign="top" style="'
        f'padding: 0; margin: 0; '
        f'font-size: 0; line-height: 0; '
        f'border: 0; vertical-align: top;'
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
        cells = ""
        for s in group:
            cid_counter += 1
            cid = f"slice_{cid_counter:03d}"
            cells += _build_cell(s.path, f"cid:{cid}", display_w, s.href, s.alt_text,
                                 s.original_width, is_base64=False)
        rows += f'<tr>\n{cells}</tr>\n'

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
        f'<table cellpadding="0" cellspacing="0" border="0" '
        f'align="center" '
        f'width="{display_w}" '
        f'style="border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt;">\n'
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
    for group in groups:
        cells = ""
        for s in group:
            cells += _build_cell(s.path, "", display_w, s.href, s.alt_text,
                                 s.original_width, is_base64=True)
        rows += f'<tr>\n{cells}</tr>\n'
    return (
        f'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
        f'"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml">\n'
        f'<head>\n'
        f'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
        f'<title>长图邮件</title>\n'
        f'</head>\n'
        f'<body style="margin: 0; padding: 0; background-color: #ffffff;">\n'
        f'<table cellpadding="0" cellspacing="0" border="0" '
        f'align="center" '
        f'width="{display_w}" '
        f'style="border-collapse: collapse;">\n'
        f'{rows}'
        f'</table>\n'
        f'</body>\n'
        f'</html>'
    )
