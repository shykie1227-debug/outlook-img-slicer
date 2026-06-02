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
    """
    path: str
    href: Optional[str] = None
    alt_text: str = ""
    sort_key: float = 0.0


def _get_img_dimensions(img_path: str) -> tuple:
    """获取图片实际像素尺寸 (width, height)"""
    with Image.open(img_path) as img:
        return img.size


def _build_image_row(slice_path: str, cid: str, display_w: int, href: Optional[str] = None, alt: str = "") -> str:
    """
    生成一张切片的 <tr>...</tr>：
      - href 为 None:  普通图，<img>
      - href 有值:    链接图，<a href="..."><img></a>
    """
    try:
        actual_w, actual_h = _get_img_dimensions(slice_path)
        display_h = round(actual_h * display_w / actual_w)
    except Exception:
        display_w, display_h = 650, 650

    # alt 默认用文件名（Outlook 图片加载失败时显示）
    if not alt:
        alt = Path(slice_path).name

    img_tag = (
        f'<img src="cid:{cid}" '
        f'width="{display_w}" '
        f'height="{display_h}" '
        f'alt="{alt}" '
        f'border="0" '
        f'style="border: 0; display: block; outline: none; text-decoration: none;" />'
    )

    if href:
        # 链接切片：<a> 包图，Outlook 桌面端可点
        # 不用 inline-block（Outlook Word 引擎忽略），用 <a> + <img> 最简结构
        inner = (
            f'<a href="{href}" target="_blank" '
            f'style="display: block; text-decoration: none; outline: none;">'
            f'{img_tag}'
            f'</a>'
        )
    else:
        inner = img_tag

    return (
        f'<tr>\n'
        f'<td align="center" style="'
        f'text-align: center; '
        f'padding: 0; margin: 0; '
        f'font-size: 0; line-height: 0; '
        f'border: 0;'
        f'">'
        f'{inner}'
        f'</td>\n'
        f'</tr>'
    )


def assemble_html(slices: List[SliceItem], display_w: int = 650) -> str:
    """
    生成适用于 Outlook 的 HTML 邮件正文（CID 内联嵌入版）。

    V4.6.7 排序架构：入口处统一 sorted(slices, key=sort_key)，输出顺序
    **唯一由 sort_key 决定**，与调用方传入的顺序无关。

    Args:
        slices: 切片列表（带/不带链接）
        display_w: 邮件中显示的图片宽度（px），默认 650
    """
    # V4.6.7：唯一排序点 — 不允许依赖任何隐式顺序
    sorted_slices = sorted(slices, key=lambda s: s.sort_key)
    rows = ""
    for i, s in enumerate(sorted_slices):
        cid = f"slice_{i + 1:03d}"
        rows += _build_image_row(s.path, cid, display_w, s.href, s.alt_text) + "\n"

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

    V4.6.7 排序架构：入口处统一 sorted(slices, key=sort_key)。
    """
    import base64
    sorted_slices = sorted(slices, key=lambda s: s.sort_key)
    rows = ""
    for i, s in enumerate(sorted_slices):
        with open(s.path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        ext = Path(s.path).suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        src = f"data:{mime};base64,{b64}"
        try:
            actual_w, actual_h = _get_img_dimensions(s.path)
            display_h = round(actual_h * display_w / actual_w)
        except Exception:
            display_w, display_h = 650, 650
        alt = s.alt_text or Path(s.path).name

        img_tag = (
            f'<img src="{src}" '
            f'width="{display_w}" height="{display_h}" '
            f'alt="{alt}" border="0" '
            f'style="border: 0; display: block; outline: none; text-decoration: none;" />'
        )
        if s.href:
            inner = (
                f'<a href="{s.href}" target="_blank" '
                f'style="display: block; text-decoration: none; outline: none;">'
                f'{img_tag}</a>'
            )
        else:
            inner = img_tag
        rows += (
            f'<tr>\n'
            f'<td align="center" style="'
            f'text-align: center; padding: 0; margin: 0; '
            f'font-size: 0; line-height: 0; border: 0;'
            f'">'
            f'{inner}'
            f'</td>\n'
            f'</tr>\n'
        )
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
