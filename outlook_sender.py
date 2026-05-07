"""
Outlook 自动化模块
通过 win32com.client 创建 Outlook 邮件，并通过 CID 嵌入式附件插入图片
V3: 支持 Content-ID (CID) 嵌入，解决图片在 Outlook 中因安全设置不显示的问题
"""
import sys


# PR_ATTACH_CONTENT_ID 的 DASL 属性名（Outlook MAPI 标准属性）
PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"


def create_email_with_images(html_content: str, image_paths: list, subject: str = "", to: str = ""):
    """
    创建 Outlook 邮件窗口，图片以 CID 嵌入式附件形式插入正文

    Args:
        html_content: 邮件正文 HTML（使用 cid:image_N@slicer 引用图片）
        image_paths: 切片后的图片路径列表
        subject: 邮件主题
        to: 收件人邮箱地址（可选）
    """
    if sys.platform != "win32":
        raise RuntimeError("此功能仅在 Windows 系统下支持 Outlook 自动化。")

    try:
        import win32com.client
        import pythoncom
    except ImportError:
        raise RuntimeError("缺少 pywin32 库，请运行 'pip install pywin32' 安装。")

    try:
        # 初始化 COM
        pythoncom.CoInitialize()

        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = olMailItem

        # ===================================================
        # 步骤 1: 先添加所有图片作为 CID 嵌入式附件
        # ===================================================
        for i, image_path in enumerate(image_paths):
            # cid 格式必须与 html_assembler.py 中一致
            cid = f"image_{i}@slicer"

            # 添加附件: olByValue(1), position=0（正文末尾插入前先加载）
            attachment = mail.Attachments.Add(
                image_path,      # 文件路径
                1,               # olByValue = 1
                0                # Position: 0 表示不指定位置，稍后通过 HTMLBody 顺序控制
            )

            # 设置 Content-ID (PR_ATTACH_CONTENT_ID)
            # 这样 HTML 中的 <img src="cid:image_N@slicer"> 就能找到对应的附件
            attachment.PropertyAccessor.SetProperty(PR_ATTACH_CONTENT_ID, cid)

        # ===================================================
        # 步骤 2: 设置邮件属性
        # ===================================================
        mail.HTMLBody = html_content
        if subject:
            mail.Subject = subject
        if to:
            mail.To = to

        # Display(False): 非模态显示，允许用户继续操作其他窗口
        mail.Display(False)

    except pythoncom.com_error as e:
        raise RuntimeError(f"COM 初始化失败: {e}\n请确保已安装 Microsoft Outlook。")
    except Exception as e:
        raise RuntimeError(f"启动 Outlook 邮件失败: {e}")
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
