# Outlook 长图无损插入工具

将长图 / 长截图自动切片后插入经典 Outlook 邮件正文。支持手动调整切线、图片按钮链接和本地 HTML 复制，全程离线且不会自动发送邮件。

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

- 🎯 **安全切片** — 高度超过 1200px 自动垂直分块，默认邮件宽度 960px
- ✋ **手动切线** — 自动切图后可拖动横线微调切开位置，内置 80–1200px 防呆范围
- 📎 **拖拽上传** — 支持 JPG / PNG / WebP / GIF / BMP / **SVG** / PDF / PPT / PPTX / **PSD** 直接拖入
- 🧠 **三重智能切图加强** — BLANK_VARIANCE / TRANSITION / TEXT_BUFFER 加严，避免切断文字
- 🎯 **可点击热区** — 在图上框选按钮位置挂 URL，使用 Outlook 支持的物理图片分段
- 🧩 **最小分片** — 只切按钮所在行，减少附件数量和 Outlook 重排风险
- 📤 **创建草稿** — Outlook COM 自动弹出预填邮件窗口，由用户检查后手动发送
- 📋 **可靠复制** — Windows CF_HTML 使用正确的 UTF-8 字节偏移，避免中文内容截断
- 🖥️ **Windows 专属** — 创建邮件需 Windows 10/11 和经典 Outlook
- 🔲 **DPI 自适应** — 完美支持高分屏（100% / 125% / 150% / 175%）
- 🧹 **临时清理** — 程序退出自动删除切片文件，无残留
- ⚙️ **免安装** — 下载双击即用，无需配置 Python 环境

---

## 🚀 快速开始

### 📥 方式一：直接下载（推荐）

<div align="center">

**[⬇️ 立即下载 Outlook长图助手绿色版](https://github.com/shykie1227-debug/outlook-img-slicer/releases/latest)**

*绿色免安装 · 约 180MB · Windows 10/11 · 解压即用*

</div>

### 📦 方式二：查看发布历史

👉 [所有 Release 版本](https://github.com/shykie1227-debug/outlook-img-slicer/releases)

### 🛠 方式三：开发环境运行

```bash
# 克隆项目
git clone https://github.com/shykie1227-debug/outlook-img-slicer.git
cd outlook-img-slicer

# 安装 Node.js 依赖
npm install

# 安装 Python 依赖（图像处理）
pip install -r requirements.txt

# 启动开发服务器
npm run dev
```

### 📦 方式四：自行打包

```bash
# 构建渲染进程和主进程
npm run build

# 打包为 Windows 绿色免安装版（需在 Windows 上执行）
npm run dist:win
# 输出: release-artifacts/electron/Outlook 长图助手-V6.0.3-portable-x64.exe

# 打包为 NSIS 安装版（可选）
npm run dist:win:nsis
# 输出: release-artifacts/electron/Outlook 长图助手-V6.0.3-Setup.exe
```

---

## 📖 使用说明

### Windows 用户

1. 下载 `Outlook 长图助手-V6.0.3-portable-x64.exe` 到任意目录
2. **双击直接运行**（无需安装，绿色免安装）
3. 将长图 / 长截图**拖入**窗口，或点击**选择文件**
4. （可选）点击**调整切图位置**拖动切线，或点击缩略图添加按钮链接
5. 填写收件人（可选）和邮件标题（可选）
6. 点击**在经典 Outlook 中创建邮件** → Outlook 自动弹出
7. 在邮件窗口中核对内容，发送！

### 支持的文件格式

| 类别 | 格式 | 说明 |
|:---|:---|:---|
| 图片 | JPG / PNG / WebP / GIF / BMP / SVG | 直接切片（SVG 自动转换为 PNG） |
| 文档 | PDF | 每页渲染为图片 |
| 幻灯片 | PPT / PPTX | 需 PowerPoint 或 LibreOffice 全保真渲染 |
| 设计稿 | PSD | 自动合并所有可见图层 |

### ✋ 手动调整切图位置（V5.0）

1. 自动切图完成后点击**调整切图位置**
2. 在整图预览中拖动橙色横线
3. 工具会自动限制每张切片至少 80px、最多 1200px
4. 点击**应用切线**后重新检查缩略图
5. 如果已经添加按钮链接，调整前会明确提示链接区域将被清空

### 🎯 可点击热区

在切片上**框选可点击区域 + 填 URL** → 邮件中该区域变成可点击链接：

1. 切片完成后点击缩略图打开热区编辑器
2. 在大图上**拖动鼠标**框选按钮位置
3. 输入 URL（如 `https://example.com/buy`）→ 添加
4. 已添加的热区用橙色虚线标注
5. 列表项右键可**改 URL / 改区域 / 删除**
6. 「复制到 Outlook」或「创建邮件」时自动生成带链接的物理图片片段

---

## 🖥️ 界面布局

```
┌─────────────────────────────────────────────────────┐
│  Outlook 长图助手 V6.0.3                            │  ← 标题栏
│  长图/PDF/PPT/PSD切片后插入Outlook邮件               │
│  1 放入文件 → 2 调整切线/添加链接 → 3 创建邮件       │
├─────────────────────────────────────────────────────┤
│      📂                                             │  ← 拖拽上传区
│   拖拽或点击上传                                    │
│   支持 JPG · PNG · PDF · PPT · PSD                  │
├─────────────────────────────────────────────────────┤
│  [重置]  邮件宽度：[960] px  [──●────]             │
│  [ ] 导出图片  [✓] 避开文字切图（推荐）             │
│  [复制到Outlook] [调整切图位置] [添加可点击按钮]     │
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
                    │ 普通图连续 <img>     │
                    │ 按钮行最小物理切片   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Outlook COM        │
                    │  直接打开邮件窗口   │
                    │  (不自动发送)       │
                    └─────────────────────┘
```

**为什么只保留一个外层表格？** 经典 Outlook 使用 Word 引擎。一个外层表格负责邮件宽度和居中，普通切片在同一单元格内连续排列；按钮所在行独立拼接，避免多层表格互相影响列宽。

**为什么不自动发送？** 邮件发送是不可逆操作——本工具仅弹出预填好的邮件窗口，由用户**手动检查后点发送**，符合「本地运行 + 用户最终决策」原则。

---

## 📁 项目结构

```
outlook-img-slicer/
├── electron/                # 🖥️ Electron 主进程
│   ├── main.ts              # 窗口管理、菜单、IPC 注册
│   ├── preload.ts           # 安全 API 暴露（contextBridge）
│   ├── ipc.ts               # IPC 路由映射
│   ├── sidecar-manager.ts   # Python 子进程管理
│   ├── dialog-handlers.ts   # 文件对话框处理
│   └── safe-file-protocol.ts # 安全文件预览协议
├── app/                     # 🎨 React 渲染进程
│   ├── src/
│   │   ├── App.tsx          # 主应用组件、工作流编排
│   │   ├── store.ts         # Zustand 全局状态管理
│   │   └── components/      # UI 组件（DropZone、CutEditor、SettingsPanel）
│   └── package.json
├── sidecar/                 # 🐍 Python Sidecar（图像处理）
│   └── sidecar_server.py    # stdio JSON-RPC 服务
├── image_slicer.py          # 🖼️ 图像切片模块（智能切图 + 加墙）
├── image_safety.py          # 🛡️ 图片安全检查
├── pdf_slicer.py            # 📄 PDF 解析模块（PyMuPDF）
├── ppt_slicer.py            # 🎬 PPT 解析模块（PowerPoint COM / LibreOffice）
├── psd_slicer.py            # 🎨 PSD 解析模块（psd-tools 合并可见图层）
├── hotspot_slicer.py        # 🎯 热区切片算法
├── clickable_map.py         # 🗺️ 热区数据结构
├── html_assembler.py        # 🧩 Outlook HTML 组装模块
├── clipboard_html.py        # 📋 Windows 剪贴板 HTML
├── outlook_sender.py        # 📬 Outlook 自动化模块（pywin32 COM）
├── requirements.txt         # 📦 Python 依赖声明
├── electron-builder.yml     # 🏭 Electron Builder 打包配置
├── build_v6.py              # 🔨 Windows 构建脚本（Python 版）
├── build_v6.ps1             # 🔨 Windows 构建脚本（PowerShell 版）
├── docs/                    # 📚 文档
│   ├── v6-build-guide.md    # V6 构建指南
│   └── dev-logs/            # 开发日志
├── tests/                   # 🧪 测试文件
├── legacy/                  # 📜 遗留代码（V5 及更早）
│   └── v5-python-ui/        # V5 PySide6 单文件版本
├── release-artifacts/       # 📦 发布说明
├── LOCAL_RULES.md           # 🔒 本地运行原则（禁联网）
└── README.md
```

### 核心模块说明

| 层级 | 文件 | 职责 |
|:---|:---|:---|
| **Electron** | `electron/main.ts` | 窗口管理、菜单、应用生命周期 |
| **Electron** | `electron/ipc.ts` | IPC 通道路由到 Sidecar |
| **Electron** | `electron/sidecar-manager.ts` | Python 子进程通信与心跳管理 |
| **React** | `app/src/App.tsx` | 主应用组件、工作流编排 |
| **React** | `app/src/store.ts` | Zustand 全局状态管理 |
| **React** | `app/src/components/` | UI 组件（DropZone、CutEditor、SettingsPanel） |
| **Python** | `sidecar/sidecar_server.py` | stdio JSON-RPC 服务端 |
| **Python** | `image_slicer.py` | 读取图片、智能切图 |
| **Python** | `html_assembler.py` | 生成 Outlook 兼容的 CID / Base64 HTML |
| **Python** | `outlook_sender.py` | 通过 `win32com.client` 启动 Outlook 并填充邮件 |

---

## 🛠 技术栈

| 类别 | 技术 |
|:---|:---|
| 语言 | TypeScript + Python 3.10+ |
| UI 框架 | Electron 30 + React 18 + Vite |
| 状态管理 | Zustand |
| 动画 | Framer Motion |
| 样式 | Tailwind CSS |
| 图像处理 | Pillow ≥ 10.0 |
| PDF / PPT 解析 | PyMuPDF ≥ 1.23 |
| PSD 解析 | psd-tools ≥ 1.10 + numpy |
| Outlook 自动化 | pywin32 ≥ 306（仅 Windows） |
| 打包 | Electron Builder (Portable 绿色免安装版 / NSIS 安装版) |
| 邮件布局 | 单外层 `<table>` + 连续图片 + 独立热区行 |

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

### Q: 为什么安装包这么大（~180MB）？
A: V6 使用 Electron 打包，内置了 Chromium 浏览器引擎 + Node.js + Python 解释器 + 图像处理库，总大小约 180MB。这是为了提供更现代化的 UI 和更好的跨平台能力。

### Q: 数据会上传吗？
A: **不会**。本工具**完全不联网、不上传、完全本地运行**。所有图片处理、HTML 生成、Outlook 邮件填充都在本机完成，详见 `LOCAL_RULES.md`。

---

## 📝 更新日志

### V6.0.3 — 2026-07-01

- ✨ **SVG 格式支持** — 支持拖入 SVG 格式图片，自动转换为 PNG 后进行切片处理
- 🐛 **Outlook 长图显示修复** — 修复复制 HTML 到 Outlook 时长图显示错乱问题，添加明确的 height 属性
- 🐛 **按钮布局修复** — 修复添加可点击按钮后发送到 Outlook 时出现的长图错乱和元素间缝隙问题，改用 table/td 结构
- ⚙️ **邮件宽度调整** — 默认邮件宽度从 650px 改为 960px，修复宽度设置无效问题
- 🚀 **性能优化** — Sidecar 通信添加超时机制，避免长时间阻塞
- 🎨 **暗色模式改进** — 添加 color-scheme CSS 变量，改善 Windows 深色模式下的滚动条和输入框显示
- 🔧 **类型安全增强** — 改进 Electron IPC 处理器的 TypeScript 类型定义

### V5.0.0 — 2026-06-29

- 修复中文 CF_HTML 偏移导致的粘贴截断。
- 热区改为逐行最小切片，减少 Outlook 附件数量和错位风险。
- 新增手动切线编辑器、三步引导和 80–1200px 防呆。
- 同名图片、文档转换页和热区中间文件使用独立临时工作区。
- 默认邮件宽度改为 650px，主操作明确标注经典 Outlook。

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
