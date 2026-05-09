"""
HTML 组装器模块
生成带内联 CSS 的表格 HTML，实现图片在 Outlook 中居中拼接
"""
from pathlib import Path
from typing import List, Dict


def assemble_html(image_paths: List[str], original_width: int = 650) -> str:
    """
    生成适用于 Outlook 的 HTML 邮件正文，图片居中显示。

    Args:
        image_paths: 切片后的图片路径列表
        original_width: 邮件中图片显示的宽度（px）

    Returns:
        完整的 HTML 字符串，使用 cid: 内联嵌入
    """
    img_tags = ""
    for i, path in enumerate(image_paths):
        cid = f"slice_{i + 1:03d}"
        img_tags += (
            f'<img src="cid:{cid}" '
            f'alt="slice_{i + 1}" '
            f'style="'
            f'display: block; '
            f'width: {original_width}px; '
            f'height: auto; '
            f'margin: 0 auto; '
            f'border: 0; '
            f'" />'
        )

    # 简洁的居中表格布局，Outlook 最稳
    html = (
        f'<table cellpadding="0" cellspacing="0" border="0" '
        f'style="margin: 0 auto; border-collapse: collapse; '
        f'text-align: center; width: {original_width}px;">'
        f'<tr>'
        f'<td style="text-align: center; width: {original_width}px; padding: 0; '
        f'font-size: 0; line-height: 0;">'
        f'{img_tags}'
        f'</td>'
        f'</tr>'
        f'</table>'
    )
    return html


def get_cid_map(image_paths: List[str]) -> Dict[int, str]:
    """
    返回 image_paths 索引到 CID 的映射，供 outlook_sender 设置附件 CID 用。
    """
    return {i: f"slice_{i + 1:03d}" for i in range(len(image_paths))}