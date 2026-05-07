"""
HTML 组装器模块
生成带内联 CSS 的表格 HTML，实现图片在 Outlook 中无缝居中拼接
V3 改进：CID 嵌入式嵌入 + CSS min-height/visibility 修复 Outlook 显示兼容性
"""
from pathlib import Path
from typing import List, Dict


def assemble_html(image_paths: List[str], original_width: int = 650) -> str:
    """
    生成适用于 Outlook 的 HTML 邮件正文（V3 CID 嵌入版）

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
            f'width="{original_width}" '
            f'alt="slice_{i + 1}" '
            f'style="'
            f'display: block; '
            f'width: {original_width}px; '
            f'border: 0; '
            f'min-height: 1px; '
            f'visibility: visible !important; '
            f'" />'
        )

    # table 布局是 Outlook 邮件最稳妥的居中方式
    html = f"""
    <!--[if mso]>
    <table cellpadding="0" cellspacing="0" border="0" width="{original_width}"><tr><td>
    <![endif]-->
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
    <!--[if mso]></td></tr></table><![endif]-->
    """
    return html.strip()


def get_cid_map(image_paths: List[str]) -> Dict[int, str]:
    """
    返回 image_paths 索引到 CID 的映射，供 outlook_sender 设置附件 CID 用。

    Returns:
        {index: "slice_001", ...}
    """
    return {i: f"slice_{i + 1:03d}" for i in range(len(image_paths))}
