"""
Outlook 自动化模块
通过 win32com.client 创建并填充 Outlook 邮件窗口
V3 改进：完整 CID 嵌入（PR_ATTACH_CONTENT_ID）+ 保存切图功能

⚠️ 本地运行原则承诺（本模块明确遵守）:
  - 只调用 mail.Display(False) 打开邮件窗口，不调用 mail.Send()
  - 不收集/上传任何用户数据
  - 不调用任何外网 API/云服务
  - 所有数据都在本地机器上处理
"""
import sys
import os
import shutil


def create_email_with_images(html_content: str, subject: str = "", to: str = "",
                            image_paths: list = None, save_dir: str = ""):
    """
    创建 Outlook 邮件窗口并填充 HTML 内容（V3 CID 版）

    Args:
        html_content: 邮件正文 HTML（使用 cid:slice_XXX）
        subject: 邮件主题
        to: 收件人邮箱地址（可选）
        image_paths: 图片路径列表（用于 CID 嵌入）
        save_dir: 若指定，则在发送前将切片保存到此目录（保存切图功能）
    """
    if sys.platform != "win32":
        raise RuntimeError("此功能仅在 Windows 系统下支持 Outlook 自动化。")

    # 保存切图功能
    if save_dir and image_paths:
        os.makedirs(save_dir, exist_ok=True)
        for path in image_paths:
            fname = os.path.basename(path)
            dst = os.path.join(save_dir, fname)
            shutil.copy2(path, dst)

    try:
        import win32com.client
        import pythoncom
    except ImportError:
        raise RuntimeError("缺少 pywin32 库，请运行 'pip install pywin32' 安装。")

    try:
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 代表 olMailItem

        # 设置邮件属性
        mail.HTMLBody = html_content
        if subject:
            mail.Subject = subject
        if to:
            mail.To = to

        # 通过 MAPI 逐个设置附件的 Content-ID（CID）
        if image_paths:
            from html_assembler import get_cid_map
            cid_map = get_cid_map(image_paths)
            for i, path in enumerate(image_paths):
                cid = cid_map[i]
                att = mail.Attachments.Add(path)
                att.PropertyAccessor.SetProperty(
                    "http://schemas.microsoft.com/mapi/proptag/0x3712001F", cid
                )

        # Display(False) 非模态显示
        # 【本地运行原则】绝不调用 mail.Send()，由用户手动检查后点发送
        mail.Display(False)

    except Exception as e:
        raise RuntimeError(f"启动 Outlook 失败: {e}")
    finally:
        pythoncom.CoUninitialize()
