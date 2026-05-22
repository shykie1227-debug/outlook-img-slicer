"""
HTML 组装器模块
生成仅用 <table> + inline-style 的 HTML，适配 Outlook 渲染引擎。
禁止使用：flex · grid · position
仅用：table · inline-style

Outlook/Word 图片渲染要点：
- 必须设 width+height 双属性，Word 才不拉伸变形
- 用 HTML width/height 属性而非 CSS（Word 对 CSS 支持差）
"""
from pathlib import Path
from typing import List, Dict
from PIL import Image


def _get_img_dimensions(img_path: str) -> tuple:
    """获取图片实际像素尺寸"""
    with Image.open(img_path) as img:
        return img.size  # (width, height)


def assemble_html(image_paths: List[str], original_width: int = 650) -> str:
    """
    生成适用于 Outlook 的 HTML 邮件正文（CID 内联嵌入版）。
    每张图读取实际尺寸，按 display_width 等比计算 height。
    """
    img_rows = ""
    for i, path in enumerate(image_paths):
        cid = f"slice_{i + 1:03d}"
        try:
            actual_w, actual_h = _get_img_dimensions(path)
            display_h = round(actual_h * original_width / actual_w)
        except Exception:
            display_h = original_width

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
            f'height="{display_h}" '
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
        f'</body>\n'
        f'</html>'
    )
    return html


def get_cid_map(image_paths: List[str]) -> Dict[int, str]:
    return {i: f"slice_{i + 1:03d}" for i in range(len(image_paths))}


def generate_plain_html(image_paths: List[str], original_width: int = 650) -> str:
    """
    生成纯内联 base64 的 HTML，供复制到剪贴板使用。
    每张图读取实际尺寸，等比计算 height，防止 Word/Outlook 拉伸变形。
    """
    import base64

    img_rows = ""
    for i, path in enumerate(image_paths):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        ext = Path(path).suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        src = f"data:{mime};base64,{b64}"

        try:
            actual_w, actual_h = _get_img_dimensions(path)
            display_h = round(actual_h * original_width / actual_w)
        except Exception:
            display_h = original_width

        img_rows += (
            f'<tr>\n'
            f'<td align="center" style="'
            f'text-align: center; padding: 0; margin: 0; '
            f'font-size: 0; line-height: 0;'
            f'">'
            f'<img src="{src}" '
            f'alt="slice_{i + 1}" '
            f'width="{original_width}" '
            f'height="{display_h}" '
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
        f'</body>\n'
        f'</html>'
    )
    return html
