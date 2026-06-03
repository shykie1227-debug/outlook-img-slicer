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
                            image_paths=None, save_dir: str = "",
                            slices=None):
    """
    创建 Outlook 邮件窗口并填充 HTML 内容（V3 CID 版）

    V4.6.7 修复：接受 slices: List[SliceItem]，按 sort_key 排序后取 paths。
    这样 image_paths（按顺序）与 html_content 里的 cid:slice_XXX 顺序完全一致。

    Args:
        html_content: 邮件正文 HTML（使用 cid:slice_XXX）
        subject: 邮件主题
        to: 收件人邮箱地址（可选）
        image_paths: 备用：纯路径列表（与 slices 二选一）
        save_dir: 若指定，则在发送前将切片保存到此目录（保存切图功能）
        slices: V4.6.7 推荐传 List[SliceItem]，按 sort_key 排序后取 path
    """
    if sys.platform != "win32":
        raise RuntimeError("此功能仅在 Windows 系统下支持 Outlook 自动化。")

    # V4.6.7：从 slices 取按 sort_key 排序的 path 列表
    # image_paths 作为向后兼容，但 slices 优先
    if slices is not None:
        from html_assembler import SliceItem
        try:
            sorted_slices = sorted(slices, key=lambda s: s.sort_key)
            sorted_paths = [s.path for s in sorted_slices]
        except AttributeError:
            # 兼容 image_paths 传 str 列表
            sorted_paths = list(slices)
    elif image_paths is not None:
        sorted_paths = list(image_paths)
    else:
        sorted_paths = []

    # 保存切图功能
    if save_dir and sorted_paths:
        os.makedirs(save_dir, exist_ok=True)
        for path in sorted_paths:
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

        # V4.6.7：按 sort_key 排序后的路径与 html 里的 cid 一一对应
        # 不再调 get_cid_map，直接 enumerate 生成 cid
        for i, path in enumerate(sorted_paths):
            cid = f"slice_{i + 1:03d}"
            att = mail.Attachments.Add(path)
            att.PropertyAccessor.SetProperty(
                "http://schemas.microsoft.com/mapi/proptag/0x3712001F", cid
            )
            att.PropertyAccessor.SetProperty(
                "http://schemas.microsoft.com/mapi/proptag/0x7FFE000B", True
            )
            ext = os.path.splitext(path)[1].lower()
            mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
            att.PropertyAccessor.SetProperty(
                "http://schemas.microsoft.com/mapi/proptag/0x370E001F", mime
            )

        # 先注册 CID 附件，再写 HTMLBody，降低 Outlook/Word 重写正文时
        # 丢失 cid 图片引用或 <a><img></a> 链接关系的概率。
        mail.HTMLBody = html_content
        if subject:
            mail.Subject = subject
        if to:
            mail.To = to

        # Display(False) 非模态显示
        # 【本地运行原则】绝不调用 mail.Send()，由用户手动检查后点发送
        mail.Display(False)

    except Exception as e:
        raise RuntimeError(f"启动 Outlook 失败: {e}")
    finally:
        pythoncom.CoUninitialize()
