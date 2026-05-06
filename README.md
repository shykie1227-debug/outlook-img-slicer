# Outlook 长图无损插入工具

将长图自动切片后插入 Outlook 邮件正文，突破 1728px 高度限制。

## 功能特性

- ✅ 支持拖拽上传图片 (JPG, PNG, BMP, WebP, GIF) 和 PDF
- ✅ 自动检测高度，智能切片（默认每片 1500px）
- ✅ 无缝拼接：HTML 表格布局确保图片无间隙
- ✅ Outlook COM 自动化：自动创建邮件窗口
- ✅ DPI 高分屏适配
- ✅ 跨平台设计（核心功能可在 macOS 测试）

## 安装

```bash
# Windows 环境
pip install -r requirements.txt

# 仅 macOS/Linux 测试（无 Outlook）
pip install PySide6 Pillow PyMuPDF
```

## 使用方法

1. 运行程序
```bash
python main.py
```

2. 拖拽图片或 PDF 到窗口，或点击"选择文件"

3. 点击"发送到 Outlook"

4. 在 Outlook 邮件窗口编辑收件人并发送

## 工作原理

```
长图 (如 800x3000px)
       ↓
   检测高度 > 1500px
       ↓
    切成 2 片
  (800x1500 + 800x1500)
       ↓
   生成 HTML 表格
       ↓
   Outlook 显示完整长图
```

## 文件结构

```
outlook-img-slicer/
├── SPEC.md            # 规格说明书
├── README.md          # 本文件
├── main.py            # PySide6 主程序
├── image_slicer.py    # 图像切片模块
├── pdf_slicer.py      # PDF 解析模块
├── html_assembler.py  # HTML 组装模块
├── outlook_sender.py  # Outlook 自动化模块
└── requirements.txt   # 依赖列表
```

## 注意事项

- 仅支持 Windows 系统（需要 Outlook 和 pywin32）
- macOS/Linux 可用于图像处理测试，但不能发送邮件
- 临时切片文件保存在系统 TEMP 目录
