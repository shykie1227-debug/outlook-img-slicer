"""
HTML 组装器模块
生成带内联 CSS 的表格 HTML，实现图片无缝拼接
"""

from typing import List


def assemble_html(image_paths: List[str], original_width: int) -> str:
    """
    生成 HTML 邮件内容（表格布局）

    Args:
        image_paths: 图片路径列表
        original_width: 原始图片宽度

    Returns:
        HTML 字符串
    """
    # 内联 CSS 样式
    css = """
    <style>
        .email-images {
            border-collapse: collapse;
            border-spacing: 0;
        }
        .email-images img {
            display: block;
            width: {width}px;
            height: auto;
            border: none;
            margin: 0;
            padding: 0;
        }
    </style>
    """.format(width=original_width)

    # 构建图片行
    rows = ""
    for path in image_paths:
        rows += f'<tr><td><img src="{path}" alt="" /></td></tr>'

    # 完整 HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    {css}
</head>
<body>
    <table class="email-images">
        {rows}
    </table>
</body>
</html>"""

    return html


def get_html_with_inline_images(image_paths: List[str], width: int) -> str:
    """
    生成内嵌图片的 HTML（使用 CID 附件方式）

    Args:
        image_paths: 图片路径列表
        width: 图片宽度

    Returns:
        HTML 字符串
    """
    css = f"""
    <style>
        .email-images {{
            border-collapse: collapse;
        }}
        .email-images img {{
            display: block;
            width: {width}px;
            height: auto;
        }}
    </style>
    """

    rows = ""
    for i, path in enumerate(image_paths):
        cid = f"image_{i}"
        rows += f'<tr><td><img src="cid:{cid}" alt="" /></td></tr>'

    return f"""<!DOCTYPE html>
<html>
<head>{css}</head>
<body>
    <table class="email-images">{rows}</table>
</body>
</html>"""
