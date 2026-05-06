# Outlook 长图无损插入工具

将长图自动切片后插入 Outlook 邮件正文，突破 1728px 高度限制。

## ⬇️ 一键下载 exe

[![Release](https://img.shields.io/github/v/release/shykie1227-debug/outlook-img-slicer?label=下载exe)](https://github.com/shykie1227-debug/outlook-img-slicer/releases/latest)

> 点击上方徽章跳转最新 Release 页面，点击 **Assets → Outlook.zip** 下载，解压后运行 `Outlook长图插入工具.exe`。

## ✨ 功能特性

- ✅ **拖拽上传**：支持 JPG, PNG, BMP, WebP, GIF, PDF
- ✅ **智能切片**：高度超过 1500px 自动垂直分块
- ✅ **无缝拼接**：HTML 表格布局，图片无间隙
- ✅ **一键发送**：Outlook COM 自动化，直接创建邮件窗口
- ✅ **DPI 适配**：完美支持 Win10/11 高分屏
- ✅ **临时清理**：程序退出自动删除切片文件

## 🖥️ 使用方法

1. 下载 [Outlook.zip](https://github.com/shykie1227-debug/outlook-img-slicer/releases/latest) 并解压
2. 双击 `Outlook长图插入工具.exe`
3. 将长图/长截图**拖入**窗口
4. 点击**发送到 Outlook**
5. 在弹出的 Outlook 邮件窗口填入收件人，发送！

## 🔧 开发说明

### 技术栈
| 模块 | 技术 |
|:---|:---|
| UI | PySide6 |
| 图像处理 | Pillow |
| PDF 解析 | PyMuPDF |
| Outlook 自动化 | pywin32 |
| 打包 | PyInstaller |

### 本地运行（开发）

```bash
# Windows
pip install -r requirements.txt
python main.py

# 仅 macOS 测试（无 Outlook）
pip install PySide6 Pillow PyMuPDF
python main.py  # 图像处理功能可用
```

### 自行打包 exe

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm outlook_img_slicer.spec
# 输出在 dist/
```

## 📐 工作原理

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

## 📁 项目结构

```
outlook-img-slicer/
├── SPEC.md                   # 规格说明书
├── README.md                 # 本文件
├── requirements.txt          # 依赖声明
├── TEST_PLAN.md             # 测试计划
├── main.py                  # PySide6 主程序
├── image_slicer.py          # 图像切片模块
├── pdf_slicer.py           # PDF 解析模块
├── html_assembler.py         # HTML 组装模块
├── outlook_sender.py        # Outlook 自动化模块
├── outlook_img_slicer.spec  # PyInstaller 打包配置
└── .github/workflows/build.yml # 自动构建 + Release 发布
```

## ⚠️ 注意事项

- 仅支持 **Windows + Outlook**（pywin32 依赖）
- exe 由 GitHub Actions 云端 Windows 构建，杀毒软件可能误报，签名后可解决
- 临时切片文件保存在 `%TEMP%` 目录，程序退出自动清理
