# Outlook 长图无损插入工具 (精简版)

将长图自动切片后插入 Outlook 邮件正文，突破 1728px 高度限制。

**⚡ 精简版特性：**

- 🚀 **极致轻量**：移除 PDF 支持，专注图片处理
- 📦 **小体积**：相比完整版减少约 50MB
- 🎯 **快速启动**：更少的依赖，更快的加载速度
- ✅ **完整功能**：保持所有图片处理和 Outlook 集成功能

## ⬇️ 一键下载（精简版）

[![Release](https://img.shields.io/github/v/release/shykie1227-debug/outlook-img-slicer?label=最新版本)](https://github.com/shykie1227-debug/outlook-img-slicer/releases/latest)

> 点击上方徽章跳转最新 Release 页面，选择对应平台下载：
>
> - **Windows 用户**：`outlook-img-slicer-lite-windows.zip`
> - **macOS 用户**：`outlook-img-slicer-lite-macos.zip`
>
> 解压后双击运行即可，无需安装 Python！

## ✨ 功能特性

- ✅ **拖拽上传**：支持 JPG, PNG, BMP, WebP, GIF
- ✅ **智能切片**：高度超过 1500px 自动垂直分块
- ✅ **无缝拼接**：HTML 表格布局，图片无间隙
- ✅ **一键发送**：Outlook COM 自动化，直接创建邮件窗口（仅 Windows）
- ✅ **DPI 适配**：完美支持 Win10/11 高分屏
- ✅ **临时清理**：程序退出自动删除切片文件
- ✅ **自动构建**：GitHub Actions 云端自动生成可执行文件

## 🖥️ 使用方法

### Windows 用户

1. 下载 `outlook-img-slicer-lite-windows.zip` 并解压
2. 双击 `Outlook长图插入工具-精简版.exe`
3. 将长图/长截图**拖入**窗口或点击**选择文件**
4. 点击**发送到 Outlook**
5. 在弹出的 Outlook 邮件窗口填入收件人，发送！

### macOS 用户

1. 下载 `outlook-img-slicer-lite-macos.zip` 并解压
2. 双击 `Outlook长图插入工具-精简版`（可能需要右键 → 打开）
3. 将长图/长截图**拖入**窗口或点击**选择文件**
4. 点击**预览 HTML** 查看切片效果
5. 复制 HTML 内容到邮件客户端使用

> 💡 **提示**：macOS 版支持完整的图像处理功能，但 Outlook 自动化功能仅在 Windows 上可用。

## 🔧 开发说明

### 技术栈

| 模块           | 技术                 |
| :------------- | :------------------- |
| UI             | PySide6 (Qt6)        |
| 图像处理       | Pillow               |
| Outlook 自动化 | pywin32 (仅 Windows) |
| 打包           | PyInstaller          |
| CI/CD          | GitHub Actions       |

### 本地运行（开发）

```bash
# 安装精简版依赖
pip install PySide6 Pillow pywin32  # Windows
pip install PySide6 Pillow          # macOS

# 运行主程序
python main.py
```

### 自动构建

项目使用 GitHub Actions 自动构建：

- **触发条件**：创建新 Release 时自动构建
- **构建平台**：Windows (exe) + macOS (app)
- **输出位置**：自动上传到 Release Assets
- **精简策略**：移除 PDF 相关依赖，减小体积

### 手动打包

```bash
# 安装打包工具
pip install pyinstaller

# 打包（会自动读取 outlook_img_slicer.spec）
pyinstaller --clean --noconfirm outlook_img_slicer.spec

# 输出在 dist/ 目录
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
outlook-img-slicer-lite/
├── 📄 README.md                 # 本文件 (精简版)
├── 📄 requirements.txt          # 精简版依赖声明
├── 📄 outlook_img_slicer.spec  # PyInstaller 打包配置
├── 🔧 main.py                  # PySide6 主程序 (移除PDF支持)
├── 🔧 image_slicer.py          # 图像切片处理模块
├── 🔧 html_assembler.py         # HTML 组装生成模块
├── 🔧 outlook_sender.py        # Outlook 自动化模块
├── 📁 tests/                   # 单元测试目录
└── 📁 .github/
    └── workflows/
        └── build.yml           # GitHub Actions 自动构建配置
```

## ⚠️ 注意事项

- **平台兼容性**：
  - Windows：完整功能（包括 Outlook 自动化）
  - macOS：图像处理 + HTML 预览（无 Outlook 集成）
- **不支持 PDF**：精简版专为图片处理优化，如需 PDF 支持请使用完整版
- **安全提醒**：可执行文件由 GitHub Actions 云端构建，杀毒软件可能误报
- **临时文件**：切片文件保存在系统临时目录，程序退出自动清理
- **系统要求**：Python 3.8+（开发环境），无需 Python（用户直接运行）

## 🔄 版本对比

| 功能           | 完整版 | 精简版 |
| :------------- | :----: | :----: |
| 图片支持       |   ✅   |   ✅   |
| PDF 支持       |   ✅   |   ❌   |
| Outlook 自动化 |   ✅   |   ✅   |
| 文件体积       | ~80MB  | ~30MB  |
| 启动速度       |  正常  |  更快  |
| 依赖数量       |  4个   |  2个   |

> 💡 **选择建议**：如果只需要处理图片文件，推荐使用精简版获得更好的性能和更小的体积。
