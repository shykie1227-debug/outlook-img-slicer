"""
Outlook 自动化模块
使用 win32com 创建邮件并插入 HTML 图片
"""

import os
from typing import List, Optional


def create_email_with_images(
    html_content: str,
    subject: str,
    to: str,
    attachments: Optional[List[str]] = None,
) -> bool:
    """
    创建 Outlook 邮件（HTML 格式）

    Args:
        html_content: HTML 内容
        subject: 邮件主题
        to: 收件人邮箱
        attachments: 附件路径列表（可选）

    Returns:
        是否成功创建邮件窗口
    """
    try:
        import win32com.client
    except ImportError:
        raise RuntimeError("pywin32 未安装，请在 Windows 环境运行")

    # 启动 Outlook
    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)  # 0 = olMailItem

    # 设置邮件属性
    mail.Subject = subject
    mail.To = to
    mail.HTMLBody = html_content

    # 添加附件
    if attachments:
        for att_path in attachments:
            if os.path.exists(att_path):
                mail.Attachments.Add(att_path)

    # 显示邮件窗口（用户手动发送）
    mail.Display(True)
    return True


def send_email_direct(
    html_content: str,
    subject: str,
    to: str,
    attachments: Optional[List[str]] = None,
) -> bool:
    """
    直接发送邮件（无需用户确认）

    Args:
        html_content: HTML 内容
        subject: 邮件主题
        to: 收件人邮箱
        attachments: 附件路径列表

    Returns:
        是否发送成功
    """
    try:
        import win32com.client
    except ImportError:
        raise RuntimeError("pywin32 未安装，请在 Windows 环境运行")

    outlook = win32com.client.Dispatch("Outlook.Application")
    mail = outlook.CreateItem(0)
    mail.Subject = subject
    mail.To = to
    mail.HTMLBody = html_content
    mail.Send()
    return True
