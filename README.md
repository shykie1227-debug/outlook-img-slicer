# Outlook 长图无损插入工具

将长图 / 长截图自动切片后插入 Outlook 邮件正文，突破邮件客户端 1728px 高度限制，100% 无损拼接。

---

## ✨ 功能特性

- 🎯 **智能切片** — 高度超过 1200px 自动垂直分块，支持任意图片格式
- 📎 **拖拽上传** — 支持 JPG / PNG / WebP / GIF / BMP / PDF / PPT / PPTX 直接拖入
- 🧩 **无缝拼接** — HTML 表格布局，Outlook 中图片零间隙
- 📤 **一键发送** — Outlook COM 自动化，自动弹出预填好的邮件窗口
- 🖥️ **跨平台** — Windows exe + macOS app 双平台可执行文件
- 🔲 **DPI 自适应** — 完美支持 Win10/11 高分屏（100% / 125% / 150%）
- 🧹 **临时清理** — 程序退出自动删除切片文件，无残留
- ⚙️ **免安装** — 下载解压即用，无需配置 Python 环境

---

## 🚀 快速开始

### 下载安装

📥 直接下载：[**Outlook长图插入工具.exe**](https://github.com/shykie1227-debug/outlook-img-slicer/releases/download/v4.5/Outlook.exe)（Windows 免安装，双击即用）

📦 发布说明：[查看 V4.5 更新 →](https://github.com/shykie1227-debug/outlook-img-slicer/releases/tag/v4.5) 
📦 所有版本：[前往 Releases 页面 →](https://github.com/shykie1227-debug/outlook-img-slicer/releases/latest)

### 开发环境运行

```bash
# 克隆项目
git clone https://github.com/shykie1227-debug/outlook-img-slicer.git
cd outlook-img-slicer

# 安装依赖
pip install -r requirements.txt

# 运行主程序
python main.py

# 运行测试
python -m pytest tests/
```

### 打包生成 exe

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm outlook_img_slicer.spec
# 输出目录: dist/Outlook长图插入工具/
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

### macOS 用户

> ⚠️ macOS 版支持完整的图像处理功能，Outlook 自动化功能暂不可用。

1. 下载并解压 `outlook-img-slicer-macos.zip`
2. 右键打开 `Outlook长图插入工具`（首次需在系统偏好设置中授权）
3. 将图片 / PDF **拖入**窗口
4. 点击**预览 HTML** 查看切片效果
5. 复制 HTML 内容，粘贴到邮件客户端使用

---

## 🖥️ 界面布局

```
┌─────────────────────────────────────────────────────┐
│  Outlook 长图无损插入                                │  ← 标题栏
│  自动识别图片/PDF，生成切片并打开Outlook邮件窗口。     │  ← 副标题
├─────────────────────────────────────────────────────┤
│                                                     │
│      📂                                             │  ← 拖拽上传区
│   拖拽或点击上传图片 / PDF / PPT                      │
│   支持 JPG、PNG、WebP、GIF、PDF                      │
│                                                     │
├─────────────────────────────────────────────────────┤
│  [选择文件]  [重置]                                 │  ← 操作按钮行
│                                                     │
│  收件人邮箱（可选）_____________________________      │  ← 收件人输入
│  邮件标题（可选）_____________________________       │  ← 标题输入
│                                                     │
│  显示宽度  [1200 px]                    ▼           │  ← 宽度设置
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  [缩略图] [缩略图] [缩略图] [缩略图]          │   │  ← 切片预览
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  已生成 3 张切片，准备发送 ✅                        │  ← 状态提示
│                                                     │
│           [ 创建 Outlook 邮件 ]                     │  ← 发送按钮
└─────────────────────────────────────────────────────┘
```

---

## ⚙️ 工作原理

```
                        ┌──────────────┐
     长图 / PDF ──────► │              │
                        │   检测高度    │
                        │  超过 1200px  │
                        │              │
                        └──────┬───────┘
                               │ 是
                    ┌──────────▼──────────┐
                    │   垂直切成多片       │
                    │  (每片 ≤ 1200px 高)  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  生成 HTML 表格     │
                    │  表格行内逐片排列    │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
     ┌────────▼────────┐             ┌─────────▼────────┐
     │  Windows: COM   │             │  macOS: 预览 HTML │
     │  直接打开 Outlook│             │  复制内容到客户端 │
     │  邮件窗口        │             │                  │
     └─────────────────┘             └──────────────────┘
```

**为什么用表格？** Outlook 对 CSS 支持残缺，`<table>` 是唯一能在所有版本 Outlook（尤其 Outlook 2007-2016）中可靠居中且无间隙拼接图片的布局方案。

---

## 📁 项目结构

```
outlook-img-slicer/
├── main.py                  # 🖥️ 主程序（PySide6 UI + 工作流编排）
├── image_slicer.py          # 🖼️ 图像切片模块（Pillow 无损切割）
├── pdf_slicer.py            # 📄 PDF 解析模块（PyMuPDF → PIL Image）
├── html_assembler.py        # 🧩 HTML 组装模块（表格布局生成）
├── outlook_sender.py         # 📬 Outlook 自动化模块（pywin32 COM）
├── requirements.txt         # 📦 Python 依赖声明
├── outlook_img_slicer.spec  # 🏗️ PyInstaller 打包配置
├── SPEC.md                  # 📐 功能规格说明
├── TEST_PLAN.md             # 🧪 测试计划
├── UI优化说明.md            # 🎨 UI 优化记录
├── 源代码.md                # 📝 核心源码说明
├── tests/                   # 🧪 单元测试目录
└── .github/
    └── workflows/
        └── build.yml        # 🤖 GitHub Actions 多平台自动构建
```

### 核心模块说明

| 文件 | 职责 |
|:---|:---|
| `main.py` | GUI 界面、事件处理、Worker 线程调度 |
| `image_slicer.py` | 读取图片、检测高度、按最大高度切片、输出临时文件 |
| `pdf_slicer.py` | 解析 PDF 页面（指定 DPI 渲染），转为 PIL Image |
| `html_assembler.py` | 将切片路径列表生成为 `<table>` HTML 字符串 |
| `outlook_sender.py` | 通过 `win32com.client` 启动 Outlook 并填充邮件 |

---

## 🛠️ 技术栈

| 类别 | 技术 |
|:---|:---|
| 语言 | Python 3.8+ |
| UI 框架 | PySide6 (Qt6) |
| 图像处理 | Pillow ≥ 10.0 |
| PDF 解析 | PyMuPDF ≥ 1.23 |
| Outlook 自动化 | pywin32 ≥ 300（仅 Windows） |
| 打包 | PyInstaller |
| CI/CD | GitHub Actions |

---

## ❓ 常见问题

### Q: 杀毒软件提示有病毒？
A: 可执行文件由 GitHub Actions 云端自动构建，签名机制可能导致误报。**工具本身无恶意代码**，可在杀毒软件中设置信任目录，或查看源码自行编译。

### Q: Windows 版提示"缺少 xxx.dll"？
A: 请安装 [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)。若仍有问题，尝试以管理员身份运行。

### Q: macOS 版本无法打开？
A: 首次运行需在**系统偏好设置 → 安全性与隐私 → 通用**中允许来自非 App Store 的应用。

### Q: 为什么不支持 macOS 的 Outlook 自动化？
A: macOS 上无法使用 pywin32（Windows 专属库）。macOS 版提供 HTML 预览，手动复制到任意邮件客户端即可。

### Q: 切片高度可以自定义吗？
A: 可以。界面上有**显示宽度**设置项，调整数值会同步影响切片计算。开发模式下可修改 `main.py` 中的 `Config.MAX_HEIGHT_PER_SLICE`（默认 1200px）。

### Q: PDF 支持多页吗？
A: 支持。PDF 的每一页都会被渲染为一张图片，并按顺序拼接为一个长图切片序列。

---

## 📝 更新日志

### [v4.3 xiaoming](https://github.com/shykie1227-debug/outlook-img-slicer/releases/tag/v4.3)
**宽度可手动输入 + 剪贴板HTML修复**
- 🎯 宽度控件：滑块+手动输入框（无箭头，仅数字）
- 📋 复制HTML：改用 QMimeData.setHtml()，Outlook 粘贴正确渲染
- 🧹 清理未使用的 import，代码更精简

### [v4.0 xiaoming](https://github.com/shykie1227-debug/outlook-img-slicer/releases/tag/v4.0)
**智能拼图 + 体积检测 + 复制HTML**
- ✨ 多图智能拼图：多张图片自动纵向合并为长图，居中拼接
- 🧠 智能切图：像素分析避免切断标题/表格
- 📦 邮件体积检测：发送前检测总大小，超限可选压缩
- 📋 一键复制HTML：纯表格布局，Outlook 可直接 Ctrl+V
- 🎨 宽度滑块控制、弹窗按钮中文优化、状态栏提示

### [v2026-05-09](https://github.com/shykie1227-debug/outlook-img-slicer/releases/tag/v2026-05-09)
**PPT/PPTX 支持 + Bug 修复**
- 新增 PPT/PPTX 幻灯片文件支持（PyMuPDF 直接渲染每页为图片）
- 修复 PNG 透明通道被强制转为黑色背景的严重 bug
- 修复切片文件扩展名与实际格式不匹配的 bug
- 优化打包体积：启用 PyInstaller strip，移除多余依赖
- 清理不再使用的 pdf2image 依赖

### [v2026-05-08-lite](https://github.com/shykie1227-debug/outlook-img-slicer/releases/tag/v2026-05-08-lite)
**轻量版发布 — 精简依赖，缩小包体积**
- 移除不必要的 hidden imports，减少打包体积
- 优化 PyInstaller 配置，exe 体积减少约 30%

### [v2026-05-07](https://github.com/shykie1227-debug/outlook-img-slicer/releases/tag/v2026-05-07)
**UI 大幅优化 + GitHub Actions 多平台构建**
- 新增 macOS 平台支持（`outlook-img-slicer-macos.zip`）
- 优化拖拽区域样式，增加悬停动效
- 新增缩略图预览网格（最多 4 列）
- GitHub Actions 自动化构建流程完善
- 添加 PDF 多页支持，每页独立渲染

### [v2026-05-06](https://github.com/shykie1227-debug/outlook-img-slicer/releases/tag/v2026-05-06)
**初版发布 — 核心功能实现**
- 图像切片：JPG / PNG / BMP / WebP / GIF
- HTML 表格无缝拼接（适配 Outlook）
- Outlook COM 自动化发送（Windows）
- PyInstaller 单文件打包

---

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。

---

> 使用过程中遇到问题？欢迎 [提交 Issue](https://github.com/shykie1227-debug/outlook-img-slicer/issues)。