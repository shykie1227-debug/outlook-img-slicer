# Outlook 长图无损插入工具

将长图 / 长截图自动切片后插入 Outlook 邮件正文，突破邮件客户端 1728px 高度限制，100% 无损拼接。

---

## ✨ 功能特性

- 🎯 **智能切片** — 高度超过 1200px 自动垂直分块，支持任意图片格式
- 📎 **拖拽上传** — 支持 JPG / PNG / WebP / GIF / BMP / PDF 直接拖入
- 🧩 **无缝拼接** — HTML 表格布局，Outlook 中图片零间隙
- 📤 **一键发送** — Outlook COM 自动化，自动弹出预填好的邮件窗口
- 📥 **保存切图** — 不发邮件也能将切片保存到本地文件夹
- 🔒 **CID 嵌入** — 图片以内联附件形式嵌入，绕过 Outlook 安全拦截
- 🖥️ **单文件 EXE** — 双击即用，无需安装 Python 环境
- 🧹 **临时清理** — 程序退出自动删除切片文件，无残留

---

## 🚀 快速开始

### 下载安装

| 平台 | 下载文件 | 说明 |
|:---|:---|:---|
| Windows | `outlook-img-slicer-windows.zip` | 解压后双击 `Outlook长图插入工具.exe` |

📦 [前往 Releases 页面下载 →](https://github.com/shykie1227-debug/outlook-img-slicer/releases/latest)

### 开发环境运行

```bash
git clone https://github.com/shykie1227-debug/outlook-img-slicer.git
cd outlook-img-slicer
pip install -r requirements.txt
python main.py
```

### 一键打包 EXE

```bash
pip install pyinstaller
python build.py
# 输出: dist/Outlook长图插入工具.exe
```

---

## 📖 使用说明

### Windows 用户

1. 下载并解压 `outlook-img-slicer-windows.zip`
2. 双击 `Outlook长图插入工具.exe` 启动程序
3. 将长图 / 长截图**拖入**窗口，或点击**选择文件**
4. 填写收件人（可选）和邮件标题（可选）
5. 点击**创建 Outlook 邮件** → Outlook 自动弹出
6. 在邮件窗口中核对内容，发送！

---

## 🔄 版本历史

### V3.0.20260507 (2026-05-07)

**核心改进：**
- ✅ **Outlook 图片显示修复** — 改用 CID 嵌入式附件（`mail.Attachments.Add` + `PR_ATTACH_CONTENT_ID`），解决因安全设置导致的图片不显示问题
- ✅ **CSS 显示 hack** — `<img>` 标签增加 `min-height: 1px; visibility: visible !important;`，防止 Outlook 误判为广告拦截
- ✅ **单文件 EXE 打包** — 移除 COLLECT 多文件模式，改用 PyInstaller `--onefile`，双击即用
- ✅ **保存切图按钮** — 新增「保存切图」功能，可将切片保存到本地，无需发送邮件
- ✅ **版本号显示** — 窗口标题栏和右下角显示 `V3.0.20260507`
- ✅ **按钮文字溢出修复** — 按钮自动设置 `MinimumSize`，各种分辨率下文字显示完整

### V2 (2026-05-06)

- 优化打包 + 修复 Bug + 全新文档

---

## 🛠️ 技术架构

```
用户拖入图片
    ↓
[image_slicer.py] 检测尺寸 → 按 1200px 高度切片 → PNG 无损保存
    ↓
[html_assembler.py] 生成 HTML（使用 cid:image_N@slicer 引用）
    ↓
[outlook_sender.py] 创建 Outlook 邮件
    → mail.Attachments.Add(path, olByValue, 0)
    → attachment.PropertyAccessor.SetProperty(PR_ATTACH_CONTENT_ID, cid)
    → mail.HTMLBody = html_content
    ↓
Outlook 邮件窗口弹出，图片以内联形式显示
```

**关键修复原理：**

旧版使用 `file://` URL，Outlook 安全策略会拦截外部图片引用。V3 将图片作为邮件附件嵌入，通过 `Content-ID` 协议引用，彻底解决显示问题。

---

## 📁 项目结构

```
outlook-img-slicer/
├── main.py              # 主程序 (PySide6 UI)
├── image_slicer.py      # 图像切片模块
├── pdf_slicer.py        # PDF 解析模块
├── html_assembler.py    # HTML 组装器 (V3: CID 嵌入)
├── outlook_sender.py    # Outlook 自动化 (V3: CID 附件)
├── build.py             # 一键打包脚本
├── outlook_img_slicer.spec  # PyInstaller 配置 (V3: onefile)
├── icon.ico             # 程序图标
└── requirements.txt     # 依赖清单
```

---

## ⚙️ 依赖

```
PySide6>=6.0
Pillow>=10.0
pywin32>=300
PyMuPDF>=1.23
```

---

## ⚠️ 常见问题

**Q: 图片在 Outlook 中不显示？**
> 请更新到 V3.0 以上版本。旧版本使用 `file://` URL 引用图片，被 Outlook 安全策略拦截。V3 使用 CID 嵌入式附件，彻底解决此问题。

**Q: macOS 能用吗？**
> macOS 版支持图片处理和 HTML 预览功能，Outlook 自动化功能不可用（需要 Windows）。

**Q: 如何调整切片高度？**
> 程序中 `Config.MAX_HEIGHT_PER_SLICE = 1200`，可根据需要修改。

---

## 📄 许可证

MIT License
