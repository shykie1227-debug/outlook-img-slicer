"""
HTML 组装器模块
生成带内联 CSS 的表格 HTML，实现图片在 Outlook 中无缝居中拼接
优化说明：增强了 HTML 结构的兼容性，确保在不同邮件客户端中显示一致。
"""
from pathlib import Path
from typing import List


def assemble_html(image_paths: List[str], original_width: int = 650) -> str:
    """
    生成适用于 Outlook 的 HTML 邮件正文

    Args:
        image_paths: 切片后的图片路径列表
        original_width: 邮件中图片显示的宽度（px）

    Returns:
        完整的 HTML 字符串
    """
    img_tags = ""
    for path in image_paths:
        file_url = Path(path).absolute().as_uri()
        img_tags += (
            f'<img src="{file_url}" '
            f'width="{original_width}" '
            f'style="display: block; width: {original_width}px; border: 0;" />'
        )

    # 使用 table 布局是 Outlook 邮件最稳妥的居中方式
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
