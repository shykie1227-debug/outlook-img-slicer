"""
Outlook 自动化模块
通过 win32com.client 创建并填充 Outlook 邮件窗口
优化说明：增加了收件人字段支持，并优化了错误提示。
"""
import sys


def create_email_with_images(html_content: str, subject: str = "", to: str = ""):
    """
    创建 Outlook 邮件窗口并填充 HTML 内容

    Args:
        html_content: 邮件正文 HTML
        subject: 邮件主题
        to: 收件人邮箱地址（可选）
    """
    if sys.platform != "win32":
        raise RuntimeError("此功能仅在 Windows 系统下支持 Outlook 自动化。")

    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 代表 olMailItem

        # 设置邮件属性
        mail.HTMLBody = html_content
        if subject:
            mail.Subject = subject
        if to:
            mail.To = to

        # Display(True) 会让窗口模态显示，Display(False) 则非模态
        mail.Display(False) 
        
    except ImportError:
        raise RuntimeError("缺少 pywin32 库，请运行 'pip install pywin32' 安装。")
    except Exception as e:
        raise RuntimeError(f"启动 Outlook 失败: {e}")
