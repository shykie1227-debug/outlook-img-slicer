"""
HTML 组装器模块
生成仅用 <table> + inline-style 的 HTML，适配 Outlook 渲染引擎。
禁止使用：flex · grid · position
仅用：table · inline-style
"""
from pathlib import Path
from typing import List, Dict


def assemble_html(image_paths: List[str], original_width: int = 650) -> str:
    """
    生成适用于 Outlook 的 HTML 邮件正文，图片居中显示。

    Outlook 使用 Word 渲染引擎，对 CSS 支持有限。
    最稳方案：只用 <table> + inline-style，不用 flex/grid/position。

    Args:
        image_paths: 切片后的图片路径列表
        original_width: 邮件中图片显示的宽度（px）

    Returns:
        完整的 HTML 字符串，使用 cid: 内联嵌入
    """
    img_rows = ""
    for i, path in enumerate(image_paths):
        cid = f"slice_{i + 1:03d}"
        img_rows += (
            f'<tr>\n'
            f'<td align="center" style="'
            f'text-align: center; '
            f'padding: 0; '
            f'margin: 0; '
            f'font-size: 0; '
            f'line-height: 0; '
            f'">'
            f'<img src="cid:{cid}" '
            f'alt="slice_{i + 1}" '
            f'width="{original_width}" '
            f'style="'
            f'display: block; '
            f'width: {original_width}px; '
            f'height: auto; '
            f'margin: 0 auto; '
            f'border: 0; '
            f'" />\n'
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
        f'style="'
        f'margin: 0 auto; '
        f'border-collapse: collapse; '
        f'text-align: center; '
        f'width: {original_width}px; '
        f'">\n'
        f'{img_rows}'
        f'</table>\n'
        f'</body>\n'
        f'</html>'
    )
    return html


def get_cid_map(image_paths: List[str]) -> Dict[int, str]:
    """返回 image_paths 索引到 CID 的映射"""
    return {i: f"slice_{i + 1:03d}" for i in range(len(image_paths))}


def generate_plain_html(image_paths: List[str], original_width: int = 650) -> str:
    """
    生成纯内联 base64 的 HTML（不含 cid），供复制到剪贴板使用。
    每张图片转为 base64 data URI 嵌入。
    """
    import base64

    img_rows = ""
    for i, path in enumerate(image_paths):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        ext = Path(path).suffix.lower().lstrip(".")
        if ext in ("jpg", "jpeg"):
            mime = "image/jpeg"
        elif ext == "png":
            mime = "image/png"
        else:
            mime = "image/png"
        src = f"data:{mime};base64,{b64}"
        img_rows += (
            f'<tr>\n'
            f'<td align="center" style="'
            f'text-align: center; padding: 0; margin: 0; '
            f'font-size: 0; line-height: 0;'
            f'">'
            f'<img src="{src}" '
            f'alt="slice_{i + 1}" '
            f'width="{original_width}" '
            f'style="'
            f'display: block; width: {original_width}px; '
            f'height: auto; margin: 0 auto; border: 0;'
            f'" />\n'
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
        f'style="margin: 0 auto; border-collapse: collapse; text-align: center; width: {original_width}px;">\n'
        f'{img_rows}'
        f'</table>\n'
        f'</body>\n'
        f'</html>'
    )
    return html
