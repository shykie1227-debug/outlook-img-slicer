"""
HTML 组装器模块
生成仅用 <table> + inline-style 的 HTML，适配 Outlook 渲染引擎。
禁止使用：flex · grid · position
仅用：table · inline-style

Outlook/Word 图片渲染要点：
- 必须设 width+height 双属性，Word 才不拉伸变形
- 用 HTML width/height 属性而非 CSS（Word 对 CSS 支持差）

可点击热区（V4.6）：
- 接受 hotspots: Dict[slice_filename, List[Hotspot]]
- 输出 <map name="hotspots_001"> + <area shape="rect" coords="x1,y1,x2,y2" href="...">
- 坐标在 HTML 中使用 display_width 等比缩放后的值（与图片实际渲染尺寸一致）
"""
from pathlib import Path
from typing import List, Dict, Optional
from PIL import Image

from clickable_map import HotspotMap, Hotspot


def _get_img_dimensions(img_path: str) -> tuple:
    """获取图片实际像素尺寸"""
    with Image.open(img_path) as img:
        return img.size  # (width, height)


def _scale_coords(x1: int, y1: int, x2: int, y2: int,
                  actual_w: int, display_w: int) -> tuple:
    """把图片原始像素坐标按 display 宽度等比缩放"""
    if actual_w <= 0 or display_w <= 0:
        return (x1, y1, x2, y2)
    ratio = display_w / actual_w
    return (
        round(x1 * ratio), round(y1 * ratio),
        round(x2 * ratio), round(y2 * ratio),
    )


def _build_map_block(map_name: str, hotspots: List[Hotspot],
                     actual_w: int, display_w: int) -> str:
    """生成单个 <map>...</map> 块"""
    if not hotspots:
        return ""
    area_tags = []
    for h in hotspots:
        x1, y1, x2, y2 = _scale_coords(h.x1, h.y1, h.x2, h.y2, actual_w, display_w)
        # alt 必填（Outlook 显示）
        alt_text = h.text or h.url or "link"
        area_tags.append(
            f'<area shape="rect" coords="{x1},{y1},{x2},{y2}" '
            f'href="{h.url}" alt="{alt_text}" target="_blank" />'
        )
    return (
        f'<map name="{map_name}">\n'
        + "\n".join(area_tags) + "\n"
        f'</map>'
    )


def assemble_html(image_paths: List[str], original_width: int = 650,
                  hotspots: Optional[HotspotMap] = None) -> str:
    """
    生成适用于 Outlook 的 HTML 邮件正文（CID 内联嵌入版）。
    每张图读取实际尺寸，按 display_width 等比计算 height。
    如果传 hotspots，则在每张切片上叠加可点击热区 <map>+<area>。
    """
    img_rows = ""
    map_blocks = []

    for i, path in enumerate(image_paths):
        cid = f"slice_{i + 1:03d}"
        slice_filename = Path(path).name
        try:
            actual_w, actual_h = _get_img_dimensions(path)
            display_h = round(actual_h * original_width / actual_w)
        except Exception:
            actual_w, display_h = original_width, original_width

        # 如果该切片有热区，则加上 usemap 属性
        usemap_attr = ""
        map_name = f"hotspots_{i + 1:03d}"
        slice_hotspots = hotspots.get(slice_filename) if hotspots else []
        if slice_hotspots:
            usemap_attr = f' usemap="#{map_name}"'
            map_blocks.append(
                _build_map_block(map_name, slice_hotspots, actual_w, original_width)
            )

        img_rows += (
            f'<tr>\n'
            f'<td align="center" style="'
            f'text-align: center; '
            f'padding: 0; margin: 0; '
            f'font-size: 0; line-height: 0;'
            f'">'
            f'<img src="cid:{cid}" '
            f'alt="slice_{i + 1}" '
            f'width="{original_width}" '
            f'height="{display_h}"{usemap_attr} '
            f'style="border: 0; display: block;" />\n'
            f'</td>\n'
            f'</tr>\n'
        )

    html = (
        f'<html xmlns="http://www.w3.org/1999/xhtml">\n'
        f'<head>\n'
        f'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
        f'<title>长图邮件</title>\n'
        f'</head>\n'
        f'<body style="margin:0;padding:0;background-color:#ffffff;">\n'
        f'<table cellpadding="0" cellspacing="0" border="0" '
        f'align="center" '
        f'style="border-collapse: collapse;" >\n'
        f'{img_rows}'
        f'</table>\n'
        + "\n".join(map_blocks) + "\n"
        f'</body>\n'
        f'</html>'
    )
    return html


def get_cid_map(image_paths: List[str]) -> Dict[int, str]:
    return {i: f"slice_{i + 1:03d}" for i in range(len(image_paths))}


def generate_plain_html(image_paths: List[str], original_width: int = 650,
                        hotspots: Optional[HotspotMap] = None) -> str:
    """
    生成纯内联 base64 的 HTML，供复制到剪贴板使用。
    每张图读取实际尺寸，等比计算 height，防止 Word/Outlook 拉伸变形。
    """
    import base64

    img_rows = ""
    map_blocks = []

    for i, path in enumerate(image_paths):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        ext = Path(path).suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        src = f"data:{mime};base64,{b64}"
        slice_filename = Path(path).name

        try:
            actual_w, actual_h = _get_img_dimensions(path)
            display_h = round(actual_h * original_width / actual_w)
        except Exception:
            actual_w, display_h = original_width, original_width

        usemap_attr = ""
        map_name = f"hotspots_{i + 1:03d}"
        slice_hotspots = hotspots.get(slice_filename) if hotspots else []
        if slice_hotspots:
            usemap_attr = f' usemap="#{map_name}"'
            map_blocks.append(
                _build_map_block(map_name, slice_hotspots, actual_w, original_width)
            )

        img_rows += (
            f'<tr>\n'
            f'<td align="center" style="'
            f'text-align: center; padding: 0; margin: 0; '
            f'font-size: 0; line-height: 0;'
            f'">'
            f'<img src="{src}" '
            f'alt="slice_{i + 1}" '
            f'width="{original_width}" '
            f'height="{display_h}"{usemap_attr} '
            f'style="border: 0; display: block;" />\n'
            f'</td>\n'
            f'</tr>\n'
        )

    html = (
        f'<html xmlns="http://www.w3.org/1999/xhtml">\n'
        f'<head>\n'
        f'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
        f'<title>长图邮件</title>\n'
        f'</head>\n'
        f'<body style="margin:0;padding:0;background-color:#ffffff;">\n'
        f'<table cellpadding="0" cellspacing="0" border="0" '
        f'align="center" '
        f'style="border-collapse: collapse;">\n'
        f'{img_rows}'
        f'</table>\n'
        + "\n".join(map_blocks) + "\n"
        f'</body>\n'
        f'</html>'
    )
    return html
