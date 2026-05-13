"""
HTML 组装器模块
生成带内联 CSS 的表格 HTML，实现图片在 Outlook 中居中拼接
"""
from pathlib import Path
from typing import List, Dict


def assemble_html(image_paths: List[str], original_width: int = 650) -> str:
    """
    生成适用于 Outlook 的 HTML 邮件正文，图片居中显示。

    Outlook 使用 Word 渲染引擎，对 CSS 支持有限。
    最稳方案：每张图独立一行 + align=center（HTML属性）+ margin:0 auto（CSS fallback）

    Args:
        image_paths: 切片后的图片路径列表
        original_width: 邮件中图片显示的宽度（px）

    Returns:
        完整的 HTML 字符串，使用 cid: 内联嵌入
    """
    # 逐片生成 img 标签，每张图独立一行、每行一个 td 居中
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

    # 外层 table：
    #   align="center"  → HTML 属性，Outlook Word 引擎最稳的居中方式
    #   margin:0 auto   → CSS fallback，双保险
    #   width 固定      → 与图片宽度一致
    html = (
        f'<html xmlns="http://www.w3.org/1999/xhtml">\n'
        f'<head>\n'
        f'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
        f'<title>长图邮件</title>\n'
        f'<!--[if mso]><style type="text/css">img {{ margin: 0 auto; }}</style><![endif]-->\n'
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
    """
    返回 image_paths 索引到 CID 的映射，供 outlook_sender 设置附件 CID 用。
    """
    return {i: f"slice_{i + 1:03d}" for i in range(len(image_paths))}