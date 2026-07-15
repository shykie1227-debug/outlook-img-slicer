# CODE-AGENT-GUIDE.md — Code Agent 开发指引

本文件给后续代码代理使用。保证界面、图标、构建、Outlook HTML 规则都按当前 **稳定 V6/PySide** 桌面架构执行。

---

## 1. 必读文档指引（DESIGN.md + SPEC.md）

开始任何修改前，必须先读：

1. **`DESIGN.md`** — 界面与交互规范（配色、字体、按钮、布局、弹窗、编辑器）
2. **`SPEC.md`** — 产品功能规格（业务流程、模块边界、验收范围）
3. **`LOCAL_RULES.md`** — 运行原则（本地运行、不联网、不上传、草稿不自动发送）
4. **`TEST_PLAN.md`** — 核心回归场景和人工验收路径
5. 当前 UI 截图（如用户提供）— 只作视觉对照，不作为仓库必需文件

如果文档和代码不一致，先修文档或测试，不要直接凭记忆改功能。

---

## 2. 架构概览

```
PySide6 (Python) 桌面应用
├── 主窗口：desktop/main.py（布局 + 状态 + 业务逻辑）
├── 切线编辑器：desktop/cut_editor.py（手动调整切图位置）
├── 热区编辑器：desktop/hotspot_editor.py（可点击按钮/热点编辑）
├── 导出弹窗：desktop/export_dialog.py（格式选择 + JPG 品质）
├── 图像处理：image_slicer.py / pdf_slicer.py / ppt_slicer.py / psd_slicer.py
├── HTML 组装：html_assembler.py（Outlook 兼容 HTML 生成）
├── 热点切片：hotspot_slicer.py + clickable_map.py
├── Outlook 通信：outlook_sender.py（COM 草稿创建）
├── 剪贴板：clipboard_html.py（Windows CF_HTML 格式）
└── 安全检查：image_safety.py（邮件体积检测）
```

**构建产物**：单 EXE（PyInstaller onefile），解压即用，无需安装。

统一构建入口：根目录 `build.py` 转发到 `desktop/build.py`，Windows VM 使用 `vm_build.ps1` 调用同一入口。

---

## 3. 配色/字号/按钮速查表

代码中通过 `Theme.PRIMARY` 等常量引用，所有色值与 DESIGN.md 保持一致。

| 常量 | 色值 | 用途 |
|------|------|------|
| `Theme.PRIMARY` | `#0065fd` | 主按钮、选中态、链接 |
| `Theme.PRIMARY_HOVER` | `#0057da` | 主按钮悬停 |
| `Theme.PRIMARY_ACTIVE` | `#0043ad` | 主按钮按下 |
| `Theme.PRIMARY_DISABLED` | `#e5e9ff` | 主按钮禁用背景 |
| `Theme.PRIMARY_TEXT` | `#ffffff` | 主按钮文字（白色） |
| `Theme.BG` | `#ffffff` | 主背景 |
| `Theme.CARD` | `#f9f9fa` | 输入框、卡片背景 |
| `Theme.GHOST_BG` | `#eff1f4` | Ghost 按钮背景 |
| `Theme.GHOST_HOVER` | `#dde1e8` | Ghost 按钮悬停 |
| `Theme.TEXT_PRIMARY` | `#0e1115` | 标题、重要文字 |
| `Theme.TEXT_SECONDARY` | `#333942` | 标签、正文 |
| `Theme.TEXT_PLACEHOLDER` | `#7f8d9f` | 占位符、辅助说明 |
| `Theme.TEXT_DISABLED` | `#b0b8c4` | 禁用文字 |
| `Theme.BORDER` | `#e7eaef` | 默认边框 |
| `Theme.BORDER_HOVER` | `#d0d5dd` | 边框悬停 |
| `Theme.BORDER_FOCUS` | `#557fff` | 输入框聚焦 |
| `Theme.SUCCESS` | `#10b981` | 成功 |
| `Theme.ERROR` | `#ef4444` | 错误 |
| `Theme.WARNING` | `#f59e0b` | 警告 |

**不要硬编码色值**。所有颜色走 `Theme` 常量。新增色值先更新 `Theme` 类和 `DESIGN.md`。

---

### 字号速查

| 用途 | 字号 | 字重 | 代码示例 |
|------|------|------|----------|
| 应用标题 | 18px | 700 | `_font("Microsoft YaHei", 18, QFont.Bold)` |
| Primary 按钮文字 | 13px | 700 | `_font("Microsoft YaHei", 13, QFont.Bold)` |
| Secondary 按钮文字 | 12px | 500 | `_font("Microsoft YaHei", 12, QFont.Medium)` |
| Ghost 按钮文字 | 11px | 400 | `_font("Microsoft YaHei", 11)` |
| 邮件标题输入框 | 12px | 400 | `_font("Microsoft YaHei", 12)` |
| 标签/副标题 | 11px | 400 | `_font("Microsoft YaHei", 11)` |
| 步骤引导条 | 10px | 500 | `_font("Microsoft YaHei", 10, QFont.Medium)` |
| 邮件品质下拉 | 10px | 400 | `_font("Microsoft YaHei", 10)` |

---

### 按钮规范（全部 999px 胶丸形）

| 类型 | 高度 | 字号 | 图标尺寸 | QSS 函数 |
|------|------|------|----------|----------|
| Primary | 42px | 13px 700 | 18px **必须白色图标** | `_btn_primary()` |
| Secondary | 42px | 12px 500 | 16px 深色图标 | `_btn_secondary()` |
| Ghost | 32px | 11px 400 | 16px 深色图标 | `_btn_ghost()` |
| 输入框 | 32px | 11px 400 | -- | `_input_style()` |
| 邮件标题输入 | 36px | 12px 400 | -- | `_input_style()` |

## 4. CRITICAL 图标规则和禁止事项

### 图标对比度规则

| 按钮背景 | 图标颜色 | 文件命名 |
|----------|----------|----------|
| `#0065fd`（Primary） | **白色** `#ffffff` | `mail-white.svg` / `check-white.svg` / `arrow-down-to-line-white.svg` |
| `#eff1f4`（Ghost） | **深色** `#0e1115` | `scissors.svg` / `rotate-ccw.svg` / `mouse-pointer-click.svg` / `clipboard-copy.svg` |
| `#ffffff`（Secondary） | **深色** `#0e1115` | `arrow-down-to-line.svg` |
| `#ef4444`（红色按钮） | **白色** `#ffffff` | `check-white.svg` |

### Toggle 按钮（调整切图 / 添加热区）
- 默认态 = Ghost（`#eff1f4`，深色图标）
- 激活态 = Primary（`#0065fd`，白色图标，需切换为 `*-white.svg`）

### Ghost disabled 态
- **只用 `opacity: 0.5`**，不改文字颜色
- 不要同时设 `color: disabled` + `opacity`（双重叠加导致过暗）

---

### 图标系统

图标目录：`icons/`（项目根目录），共 13 个 SVG 文件。

### 图标清单

| 文件名 | 用途 | 深色/白色 |
|--------|------|-----------|
| `upload-cloud.svg` | 拖放区上传（folder-open 造型） | 深色 |
| `rotate-ccw.svg` | 重置按钮 | 深色 |
| `scissors.svg` | 调整切图位置 | 深色 |
| `mouse-pointer-click.svg` | 添加可点击按钮 | 深色 |
| `mail-white.svg` | 创建邮件 Primary 按钮 | 白色 |
| `arrow-down-to-line.svg` | 保存切图 / 压缩按钮 | 深色 |
| `clipboard-copy.svg` | 复制图片（兼容方式） | 深色 |
| `image.svg` | 导出图片复选框 | 深色 |
| `check.svg` | 状态切换图标 / 导出弹窗复选框 | 深色 |
| `check-white.svg` | 热区编辑器确认按钮 | 白色 |
| `arrow-down-to-line-white.svg` | 导出弹窗确认按钮 | 白色 |
| `palette.svg` | 原画质按钮 | 深色 |
| `folder-open.svg` | 导出弹窗浏览文件夹 | 深色 |

### 图标风格：彩色填充

- 24x24 viewBox，Qt 缩放到实际尺寸（16-56px）
- 直接彩色路径（无圆形底座），stroke-width: 2，stroke-linecap: round，stroke-linejoin: round
- 每个图标独立主题色：teal、orange、violet、green、indigo、purple、pink
- 拖放区文件夹图标渲染尺寸 56px，Ghost/Secondary 按钮图标 16px，Primary 按钮图标 18px
- 深色图标：彩色 stroke/fill（如 `stroke="#14b8a6"`）
- 白色变体：`stroke="#ffffff"` 或 `fill="#ffffff"`（用于 Primary 蓝底按钮）
- 文件夹类图标（upload-cloud、folder-open）：黄色拟物风格（`#f6c744` 主体 + `#e5a800` 翻盖）

### 加载方式

```python
_icon("mail")                    # 加载 icons/mail.svg
_icon("mail", color="#ffffff")   # 先找 mail-white.svg，没有则动态着色
```

### SVG 规则（CRITICAL）
- **禁止 `currentColor`**（Qt SVG 渲染不支持）
- **禁止 `linearGradient`、`feDropShadow` 等滤镜**（Qt 渲染不稳定）
- 所有颜色必须使用显式 hex 值（`#f6c744`、`#ffffff`、`#14b8a6` 等）
- 统一 24x24 viewBox
- 图标尺寸由 QIcon 自动缩放，不要设固定宽高

### 新增图标规则
- 必须使用彩色填充风格（24x24，彩色 stroke/fill，无圆形底座）
- 深色版存为 `name.svg`，白色版存为 `name-white.svg`
- 不要添加未在代码中引用的图标——保持 `icons/` 目录整洁

---

## 5. 项目结构和文件说明

```
outlook-img-slicer/
├── desktop/                         # 主代码目录
│   ├── main.py                      # PySide6 主窗口、状态、业务逻辑
│   ├── cut_editor.py                # 切线编辑器对话框
│   ├── hotspot_editor.py            # 热区编辑器对话框
│   ├── export_dialog.py             # 导出格式弹窗（PNG/JPG + 品质）
│   ├── build.py                     # PyInstaller 构建脚本
│   ├── outlook_img_slicer.spec      # PyInstaller onefile 配置
│   ├── ui-preview.html             # 浏览器 UI 预览（1:1 对照）
│   └── version_info.txt            # Windows EXE 版本信息
├── image_slicer.py                  # 图片/PDF/PPT/PSD 切片引擎
├── html_assembler.py                # Outlook HTML 组装
├── hotspot_slicer.py                # 热点最小切片
├── clickable_map.py                 # 热点数据模型
├── clipboard_html.py                # Windows CF_HTML 剪贴板
├── outlook_sender.py                # Outlook COM 草稿
├── image_safety.py                  # 邮件体积检测
├── pdf_slicer.py                    # PDF 解析
├── ppt_slicer.py                    # PPT 解析
├── psd_slicer.py                    # PSD/PSB 解析（懒加载）
├── icons/                           # 13 个彩色填充风格 SVG 图标（24x24 viewBox）
├── icon.ico                         # Windows 窗口图标
├── tests/                           # 自动化测试
├── build.py                         # 根构建入口
├── DESIGN.md                        # 设计系统规范（权威来源）
├── SPEC.md                          # 产品功能规格
├── TEST_PLAN.md                     # 测试计划
├── LOCAL_RULES.md                   # 本地运行/隐私红线
├── CODE-AGENT-GUIDE.md             # 本文件
└── requirements.txt                # Python 依赖
```

---

## 6. CSS 类命名约定

- **Qt/UIA 对象名**：使用稳定英文语义名（如 `resetButton`、`mailWidthInput`），供自动化测试定位
- **Python 常量**：`Theme.XXX` 大写语义名
- **邮件 HTML**：内联样式 `outlook-` 前缀（如有 class）
- **不新增无来源的色值/字号/圆角**——先更新 `DESIGN.md`，再实现

---

### 禁止事项

1. **禁止恢复旧前端/多进程壳架构** — 只用稳定 V6/PySide 架构
2. **禁止引入运行时联网、遥测、自动更新、云上传**
3. **禁止 `mail.Send()`** — 只能 `mail.Display(False)` 打开草稿
4. **禁止 `currentColor`** — SVG 必须显式颜色
5. **禁止 `linearGradient` / `feDropShadow`** — SVG 只用纯 stroke
6. **禁止 Ghost disabled 双重叠加** — 只用 opacity 0.5
7. **禁止随意改 Outlook HTML 布局** — 遵循 `html_assembler.py` 现有模式
8. **禁止中文文件名构建产物** — 统一英文 ASCII
9. **禁止硬编码色值** — 走 `Theme` 常量
10. **禁止热区按钮共享全局 grid** — 热点行必须独立最小切片
11. **禁止添加未引用的图标文件** — `icons/` 只保留代码中实际使用的 SVG

---

## 7. 提交前的检查清单

- [ ] 已阅读 `DESIGN.md` + `SPEC.md` + `LOCAL_RULES.md`
- [ ] 所有色值走 `Theme` 常量，无硬编码
- [ ] Primary 按钮图标用了白色变体（`-white.svg`）
- [ ] SVG 无 `currentColor`、无渐变、无滤镜
- [ ] Ghost disabled 只用 opacity 0.5
- [ ] `icons/` 目录无未引用的 SVG 文件
- [ ] 版本源同步：`main.py` VERSION + `version_info.txt` + `ui-preview.html`
- [ ] 发布一致性测试已核对 README、SPEC、HANDOFF、TEST_PLAN、CHANGELOG、manifest 和发布文件名
- [ ] Outlook 草稿只调用 `mail.Display(False)`
- [ ] 构建产物英文 ASCII 文件名
- [ ] `python3 -m pytest tests/ -q` 通过
- [ ] `python3 -m py_compile build.py desktop/*.py image_slicer.py html_assembler.py outlook_sender.py clipboard_html.py clickable_map.py hotspot_slicer.py image_safety.py pdf_slicer.py ppt_slicer.py psd_slicer.py` 通过
- [ ] `git diff --check` 无空白错误

---

## 8. 布局结构（3 步分区）

```
[标题栏 40px — Outlook 长图助手 V6.3.0]
[应用标题 18px + 副标题 11px]
[引导药丸 10px：1 放入文件 → 2 调整切线/添加链接 → 3 创建邮件]

[Step 1: 放入文件]
  ├─ 拖放区（56px 文件夹图标 + 标题 14px + 提示 11px）
  └─ 工具栏行：重置(32px) | 邮件宽度输入(32px) px │ 导出图片 │ 避开文字切图

[Step 2: 编辑切片与链接]
  └─ 工具栏行：复制图片（兼容方式） | 调整切图位置 | 添加可点击按钮

[Step 3: 检查并输出]
  ├─ 邮件标题输入框(36px)
  ├─ 邮件品质下拉(30px)
  ├─ 状态提示(11px)
  └─ 底部按钮行：在 Outlook 中创建邮件(Primary 42px) | 保存切图(Secondary 42px)

[版本号 V6.3.0 + 作者]
```

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+O | 选择文件 |
| Ctrl+V | 粘贴图片 |
| Ctrl+Enter | 创建 Outlook 邮件（按钮启用时） |
| Esc | 重置（有切片时弹确认对话框） |

### 复选框

| 复选框 | 默认 | 图标 | 功能 |
|--------|------|------|------|
| 导出图片 | 关闭 | image.svg 16px | 切图模式 ↔ 导出模式切换 |
| 避开文字切图（推荐） | 开启 | 无 | 智能避开文字区域切图 |

### ui-preview.html 同步

`desktop/ui-preview.html` 是浏览器 1:1 预览，修改 main.py 布局时必须同步更新。尺寸规范见 `DESIGN.md` 第 8 节。
