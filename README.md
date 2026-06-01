# Outlook 长图无损插入工具

将长图 / 长截图自动切片后插入 Outlook 邮件正文，突破邮件客户端 1728px 高度限制，100% 无损拼接。

<p align="center">
  <a href="https://github.com/shykie1227-debug/outlook-img-slicer/releases/latest">
    <img src="https://img.shields.io/badge/下载-Outlook长图插入工具.exe-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="下载最新版本" />
  </a>
</p>

<p align="center">
  <a href="https://github.com/shykie1227-debug/outlook-img-slicer/releases/latest">📦 最新 Release</a> ·
  <a href="#使用说明">📖 使用说明</a> ·
  <a href="#更新日志">📝 更新日志</a> ·
  <a href="https://github.com/shykie1227-debug/outlook-img-slicer/issues">🐛 提交 Issue</a>
</p>

---

## ✨ 功能特性

- 🎯 **智能切片** — 高度超过 1200px 自动垂直分块，支持任意图片格式
- 📎 **拖拽上传** — 支持 JPG / PNG / WebP / GIF / BMP / PDF / PPT / PPTX / **PSD** 直接拖入
- 🧠 **三重智能切图加强** — BLANK_VARIANCE / TRANSITION / TEXT_BUFFER 加严，避免切断文字
- 🎯 **可点击热区** — 在图上框选按钮位置挂 URL，邮件里点击跳转（Outlook `<map>+<area>` 热点）
- 🧩 **无缝拼接** — HTML 表格布局，Outlook 中图片零间隙
- 📤 **一键发送** — Outlook COM 自动化，自动弹出预填好的邮件窗口
- 🖥️ **Windows 专属** — 仅支持 Windows 10/11，需安装 Microsoft Outlook
- 🔲 **DPI 自适应** — 完美支持高分屏（100% / 125% / 150% / 175%）
- 🧹 **临时清理** — 程序退出自动删除切片文件，无残留
- ⚙️ **免安装** — 下载双击即用，无需配置 Python 环境

---

## 🚀 快速开始

### 📥 方式一：直接下载（推荐）

<div align="center">

**[⬇️ 立即下载 Outlook长图插入工具.exe](https://github.com/shykie1227-debug/outlook-img-slicer/releases/latest)**

*单文件 92MB · Windows 10/11 · 免安装 · 双击即用*

</div>

### 📦 方式二：查看发布历史

👉 [所有 Release 版本](https://github.com/shykie1227-debug/outlook-img-slicer/releases)

### 🛠 方式三：开发环境运行

```bash
# 克隆项目
git clone https://github.com/shykie1227-debug/outlook-img-slicer.git
cd outlook-img-slicer

# 安装依赖
pip install -r requirements.txt

# 运行主程序
python main.py
```

### 📦 方式四：自行打包

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm outlook_img_slicer.spec
# 输出目录: dist/Outlook长图插入工具/
```

---

## 📖 使用说明

### Windows 用户

1. 下载并双击 `Outlook长图插入工具.exe` 启动程序
2. 将长图 / 长截图**拖入**窗口，或点击**选择文件**
3. （可选）调整宽度、勾选智能切图、添加可点击热区
4. 填写收件人（可选）和邮件标题（可选）
5. 点击**创建 Outlook 邮件** → Outlook 自动弹出
6. 在邮件窗口中核对内容，发送！

### 支持的文件格式

| 类别 | 格式 | 说明 |
|:---|:---|:---|
| 图片 | JPG / PNG / WebP / GIF / BMP | 直接切片 |
| 文档 | PDF | 每页渲染为图片 |
| 幻灯片 | PPT / PPTX | 需 PowerPoint 或 LibreOffice 全保真渲染 |
| 设计稿 | PSD | 自动合并所有可见图层 |

### 🎯 可点击热区（V4.6.1 新功能）

在切片上**框选可点击区域 + 填 URL** → 邮件中该区域变成可点击链接：

1. 切片完成后点击缩略图打开热区编辑器
2. 在大图上**拖动鼠标**框选按钮位置
3. 输入 URL（如 `https://example.com/buy`）→ 添加
4. 已添加的热区用橙色虚线标注
5. 列表项右键可**改 URL / 改区域 / 删除**
6. 「复制 HTML」或「发送邮件」时自动嵌入 `<map>+<area>` 热点

---

## 🖥️ 界面布局

```
┌─────────────────────────────────────────────────────┐
│  Outlook 长图助手 V4.6.1                            │  ← 标题栏
│  长图/PDF/PPT/PSD切片后插入Outlook邮件               │
├─────────────────────────────────────────────────────┤
│      📂                                             │  ← 拖拽上传区
│   拖拽或点击上传                                    │
│   支持 JPG · PNG · PDF · PPT · PSD                  │
├─────────────────────────────────────────────────────┤
│  [重置]  宽度：[960] px  [───●────]                │
│         [ ] 智能切图   [📋 复制HTML] [🎯 添加按钮] │
├─────────────────────────────────────────────────────┤
│  邮件标题（可选）_____________________________      │
├─────────────────────────────────────────────────────┤
│  [缩略图] [缩略图] [缩略图] [缩略图]                │  ← 切片预览
├─────────────────────────────────────────────────────┤
│           [ 创建 Outlook 邮件 ]  [ 保存切图 ]      │
└─────────────────────────────────────────────────────┘
```

---

## ⚙️ 工作原理

```
                        ┌──────────────┐
     长图 / PDF ──────► │              │
     PPT / PSD          │   检测高度    │
                        │  超过 1200px  │
                        │              │
                        └──────┬───────┘
                               │ 是
                    ┌──────────▼──────────┐
                    │  智能切图（可选）     │
                    │  寻找文字间空白带     │
                    │  避免切到正文        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  生成 HTML 表格     │
                    │  + 可点击热区 <map>  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Outlook COM        │
                    │  直接打开邮件窗口   │
                    │  (不自动发送)       │
                    └─────────────────────┘
```

**为什么用表格？** Outlook 对 CSS 支持残缺，`<table>` 是唯一能在所有版本 Outlook（尤其 Outlook 2007-2016）中可靠居中且无间隙拼接图片的布局方案。

**为什么不自动发送？** 邮件发送是不可逆操作——本工具仅弹出预填好的邮件窗口，由用户**手动检查后点发送**，符合「本地运行 + 用户最终决策」原则。

---

## 📁 项目结构

```
outlook-img-slicer/
├── main.py                  # 🖥️ 主程序（PySide6 UI + 工作流编排）
├── image_slicer.py          # 🖼️ 图像切片模块（智能切图 + 加墙）
├── pdf_slicer.py            # 📄 PDF 解析模块（PyMuPDF）
├── ppt_slicer.py            # 🎬 PPT 解析模块（PowerPoint COM / LibreOffice）
├── psd_slicer.py            # 🎨 PSD 解析模块（psd-tools 合并可见图层）
├── clickable_map.py         # 🎯 可点击热区数据层
├── hotspot_editor.py        # 🎯 热区交互编辑器
├── html_assembler.py        # 🧩 HTML 组装模块（表格 + <map> 热区）
├── outlook_sender.py        # 📬 Outlook 自动化模块（pywin32 COM）
├── image_safety.py          # 🛡️ 图片安全检查
├── requirements.txt         # 📦 Python 依赖声明
├── outlook_img_slicer.spec  # 🏭 PyInstaller 打包配置
├── LOCAL_RULES.md           # 🔒 本地运行原则（exe 运行时禁联网）
├── build.py                 # 🏗️ Windows 打包脚本
└── version_info.txt         # 📌 Windows 版本元信息
```

### 核心模块说明

| 文件 | 职责 |
|:---|:---|
| `main.py` | GUI 界面、事件处理、Worker 线程调度 |
| `image_slicer.py` | 读取图片、智能切图（避免文字）、按最大高度切片 |
| `pdf_slicer.py` | 解析 PDF 页面（指定 DPI 渲染） |
| `ppt_slicer.py` | 解析 PPT/PPTX（PowerPoint COM 优先，LibreOffice 备选） |
| `psd_slicer.py` | 解析 PSD 文档（合并所有可见图层） |
| `clickable_map.py` | 热区数据模型（Hotspot + HotspotMap） |
| `hotspot_editor.py` | 热区交互编辑器（拖框选 + URL 编辑） |
| `html_assembler.py` | 将切片生成为 `<table>` HTML + `<map>` 热区 |
| `outlook_sender.py` | 通过 `win32com.client` 启动 Outlook 并填充邮件 |

---

## 🛠 技术栈

| 类别 | 技术 |
|:---|:---|
| 语言 | Python 3.8+ |
| UI 框架 | PySide6 (Qt6) |
| 图像处理 | Pillow ≥ 10.0 |
| PDF / PPT 解析 | PyMuPDF ≥ 1.23 |
| PSD 解析 | psd-tools ≥ 1.10 + numpy |
| Outlook 自动化 | pywin32 ≥ 306（仅 Windows） |
| 打包 | PyInstaller 6.0 |
| 邮件布局 | HTML `<table>` + inline style + `<map>` 热区 |

---

## ❓ 常见问题

### Q: 杀毒软件提示有病毒？
A: 可执行文件由 PyInstaller 打包，未做代码签名可能被部分杀软误报。**工具本身无恶意代码**（仅通过 Outlook COM `Display()` 打开邮件窗口，不联网不上传），可在杀软中设置信任目录，或查看源码自行编译。

### Q: Windows 版提示"缺少 xxx.dll"？
A: 请安装 [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)。若仍有问题，尝试以管理员身份运行。

### Q: 智能切图和等分切图的区别？
A: 智能切图会扫描图像寻找**文字之间的空白带**作为切点（避免切断正文）；等分切图按固定高度（默认 1200px）平均切分。**默认推荐等分切图**——只有当图片含密集文字且不想切断时，勾选智能切图。

### Q: 切片高度可以自定义吗？
A: 可以。界面上有**显示宽度**设置项，调整数值会同步影响切片计算。开发模式下可修改 `main.py` 中的 `Config.MAX_HEIGHT_PER_SLICE`（默认 1728px）。

### Q: 不会自动发送邮件吗？
A: 不会。本工具**仅打开 Outlook 邮件窗口**并预填内容，发送动作由用户手动完成——这是有意设计，避免误发。

### Q: PDF / PPT / PSD 支持多页吗？
A: PDF 每页独立渲染为图片后切片；PPT 每页幻灯片独立渲染；PSD 单文档多图层，合并后单张切片。

### Q: 为什么 exe 这么大（92MB）？
A: PyInstaller 单文件打包内置了 Python 解释器 + PySide6 + Pillow + PyMuPDF + psd-tools + numpy 等全部依赖，约 92MB。如需更小体积可改用 `--onedir` 模式（多文件目录）。

### Q: 数据会上传吗？
A: **不会**。本工具**完全不联网、不上传、完全本地运行**。所有图片处理、HTML 生成、Outlook 邮件填充都在本机完成，详见 `LOCAL_RULES.md`。

---

## 📝 更新日志

### [V4.6.1 xiaoming](https://github.com/shykie1227-debug/outlook-img-slicer/releases/latest) — 2026-06-01

**PSD 支持 + 可点击热区 + 智能切图三重加强**

#### ✨ 新功能
- 🎨 **PSD 直接切图** — 拖入 `.psd` 文件，自动合并所有可见图层，文字/形状/图层蒙版/混合模式均正确合成
- 🎯 **可点击热区** — 在切片上框选按钮位置 + 挂 URL，邮件中点击区域跳转（Outlook `<map>+<area>`）
- 🎯 **热区编辑能力** — 列表项双击改 URL、右键改区域/删除
- 🎨 **可访问热区编辑器** — 切片缩略图点击 → 弹出大图编辑对话框

#### 🛡 防呆设计（5 道闸）
- 未选区域 / 未填 URL → 友好提示
- 区域 < 5×5px → 提示重选
- 重复区域 → 提示
- 裸域名 → 自动补 `https://`
- 错误数据反序列化不崩

#### 🧠 智能切图三重加强
- `BLANK_VARIANCE_THRESHOLD` 10→**6**（更严）
- `BLANK_TRANSITION_MAX` 0.06→**0.04**（更严）
- `SMART_MIN_SPACING` 16→**20**（更严）
- `SMART_TEXT_BUFFER` 28→**32**（更严）
- `_is_text_like` 改用**并集判定**，防漏检小字号/反白文字

#### 🐛 Bug 修复
- **PPT「图是图字是字」** — 改用 PowerPoint COM / LibreOffice 全保真渲染（之前退到 python-pptx 方案只提取嵌入图片）
- **PSD 启动失败** — 修复 psd-tools 隐式 numpy 依赖打包遗漏
- **UI 滑块和文字重叠** — 工具栏拆为两行，最小窗口 720×720

#### 🔒 本地运行承诺
- 明确 `outlook-slicer.exe` 在其他电脑运行时不联网/不上传（`LOCAL_RULES.md`）
- 移除「按钮文字」输入框（图片本身已有文字，只标可点击区域）
- 智能切图默认**未勾选**（等分切图为默认）

---

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。

---

> 使用过程中遇到问题？欢迎 [提交 Issue](https://github.com/shykie1227-debug/outlook-img-slicer/issues) ·
> 本工具 **完全不联网、不上传、完全本地运行** — 详见 [LOCAL_RULES.md](./LOCAL_RULES.md)
