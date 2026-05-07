"""
HTML 组装器模块
生成带 CID 引用的 HTML，实现图片在 Outlook 中以内联方式无缝拼接
V3: 使用 cid: 协议替代 file://，解决 Outlook 安全拦截导致的图片不显示问题
"""
from typing import List


def assemble_html(image_paths: List[str], original_width: int = 650) -> str:
    """
    生成适用于 Outlook 的 HTML 邮件正文（使用 CID 引用嵌入图片）

    Args:
        image_paths: 切片后的图片路径列表
        original_width: 邮件中图片显示的宽度（px）

    Returns:
        完整的 HTML 字符串（使用 cid:src 引用附件）
    """
    img_tags = ""
    for i, path in enumerate(image_paths):
        # 使用 cid:image_N@slicer 格式引用嵌入式附件
        # CSS hack: min-height:1px + visibility:visible 防止 Outlook 将零边距图片误判为广告拦截
        img_tags += (
            f'<img src="cid:image_{i}@slicer" '
            f'width="{original_width}" '
            f'alt="" '
            f'style="'
            f'display: block; '
            f'width: {original_width}px; '
            f'min-height: 1px; '          # 防止 Outlook 误判为广告
            f'visibility: visible !important; '  # 强制显示
            f'border: 0; '
            f'margin: 0; '
            f'padding: 0; '
            f'"/>'
        )

    # 使用 table 布局是 Outlook 邮件最稳妥的居中方式
    html = f"""<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
</head>
<body>
<div style="text-align: center;">
    <table cellpadding="0" cellspacing="0" border="0"
           style="margin: 0 auto; border-collapse: collapse; width: {original_width}px;">
        <tr>
            <td style="padding: 0; margin: 0;">
                {img_tags}
            </td>
        </tr>
    </table>
</div>
</body>
</html>"""
    return html.strip()


def assemble_html_legacy(image_paths: List[str], original_width: int = 650) -> str:
    """
    生成适用于非 Outlook 邮件客户端的 HTML（使用 file:// 引用）
    保留用于 macOS/预览功能
    """
    img_tags = ""
    for path in image_paths:
        from pathlib import Path
        file_url = Path(path).absolute().as_uri()
        img_tags += (
            f'<img src="{file_url}" '
            f'width="{original_width}" '
            f'style="display: block; width: {original_width}px; border: 0;" />'
        )

    html = f"""
<div style="text-align: center;">
    <table cellpadding="0" cellspacing="0" border="0"
           style="margin: 0 auto; border-collapse: collapse; width: {original_width}px;">
        <tr>
            <td style="padding: 0; margin: 0;">
                {img_tags}
            </td>
        </tr>
    </table>
</div>
    """
    return html.strip()
