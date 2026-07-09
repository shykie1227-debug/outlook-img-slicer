# Outlook 长图助手

一个给经典 Outlook 使用的 Windows 桌面小工具：把长图、PDF、PPT、PSD 等内容转成适合 Outlook 邮件正文的图片切片，并支持手动调整切图位置、添加可点击按钮链接、复制 HTML 或创建 Outlook 草稿。

当前发布架构：`稳定 V6/PySide 桌面界面 + Python 图像处理 + Outlook COM`。

## 主要能力

- 支持 JPG / PNG / WebP / GIF / BMP / SVG / PDF / PPT / PPTX / PSD / PSB。
- 自动切图并尽量避开文字区域，默认单张切片最大高度 1200px。
- 可手动调整切图位置，带最小/最大切片高度防呆。
- 可在图片按钮区域添加 URL，发送到经典 Outlook 后区域可点击。
- 可创建 Outlook 草稿窗口，但绝不自动发送邮件。
- 可复制 HTML，适合需要手动粘贴的场景。
- 全程本地处理，exe 运行时不联网、不上传。

## 用户使用

1. 打开 `OutlookImgSlicer-V6.1.1.exe`。
2. 拖入图片、PDF、PPT 或 PSD 文件。
3. 按需调整邮件宽度、手动切线或添加可点击按钮。
4. 点击“在 Outlook 中创建邮件”，在 Outlook 草稿窗口中检查后手动发送。

## 开发运行

```bash
python3 -m pip install -r requirements.txt
python3 desktop/main.py
```

## Windows 构建

在 Windows 上双击：

```text
build.bat
```

或在 PowerShell 里运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
```

输出：

```text
dist/OutlookImgSlicer-V6.1.1.exe
```

本地 Parallels Windows VM 构建入口：

```powershell
\\Mac\Home\outlook-img-slicer\vm_start_build.ps1
```

## 项目结构

```text
outlook-img-slicer/
├── desktop/                    # PySide6 桌面界面与 PyInstaller 配置
│   ├── main.py                 # 主窗口和完整工作流
│   ├── cut_editor.py           # 手动切图编辑器
│   ├── hotspot_editor.py       # 可点击按钮/热区编辑器
│   ├── export_dialog.py        # 图片导出设置
│   ├── build.py                # PyInstaller 构建脚本
│   └── outlook_img_slicer.spec # 单文件 EXE 打包配置
├── image_slicer.py             # 图片切片与智能切图
├── pdf_slicer.py               # PDF 渲染
├── ppt_slicer.py               # PPT/PPTX 渲染
├── psd_slicer.py               # PSD/PSB 合成
├── hotspot_slicer.py           # 热区物理切片
├── html_assembler.py           # Outlook HTML 生成
├── clipboard_html.py           # Windows CF_HTML
├── outlook_sender.py           # Outlook COM 草稿创建
├── tests/                      # Python 回归测试
├── build.py                    # 根构建入口，委托 desktop/build.py
├── build.ps1 / build.bat       # Windows 手动构建入口
└── vm_build.ps1                # 本地 Windows VM 构建入口
```

## 安全原则

- exe 运行时不访问网络。
- exe 运行时不上传用户文件。
- Outlook 只调用 `Display()` 打开草稿，不调用 `Send()` 自动发送。
- 用户必须在 Outlook 草稿窗口中自行检查并手动发送。
