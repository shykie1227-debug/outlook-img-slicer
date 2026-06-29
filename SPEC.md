# Outlook 长图无损插入工具 — 技术规格说明书 (SPEC.md)

> **版本: v5.0.0.20260629**

## V5 可靠性与体验升级

- 经典 Outlook 为主要邮件目标；继续使用 CID 内联附件，只打开草稿窗口，禁止自动发送。
- 普通长图沿用 V3 单表格、单单元格、连续 `<img>` 的稳定结构。
- 热区按视觉行最小切片，不再把所有按钮边界扩散成全局网格。
- 复制 HTML 的 CF_HTML 偏移按 UTF-8 字节计算，中文文件名和中文替代文字不会截断。
- 自动切图后支持拖动横线手动调整切图位置；每片强制保持 80–1200px。
- 每次处理使用独立临时工作区，避免同名文件和多实例互相覆盖。
- 主界面提供三步功能引导，默认邮件宽度为 650px。

## 1. 项目概述

### 1.1 背景
Outlook 邮件正文对图片有 **1728px 高度限制**，当用户尝试插入超过此限制的长图时，Outlook 会自动压缩或截断图片，导致长图内容丢失或质量严重下降。本工具旨在解决这一痛点。

### 1.2 目标
实现一个 Windows 桌面工具，用户将超长图片拖入工具，工具自动将图片按 Outlook 可接受的最大尺寸切片为多张子图，无损插入 Outlook 邮件正文，保证图片内容完整且清晰度不变。

### 1.3 约束
- **平台：** Windows（依赖 pywin32 实现 Outlook 自动化）
- **Python：** 3.10+
- **打包：** PyInstaller --onefile 单文件 exe
- **无网络依赖：** 最终 EXE 纯本地运行，不上传任何数据

## V3 改进清单

| 改进项 | 说明 |
|---|---|
| 单文件 EXE | `--onefile` 模式，双击即用 |
| CID 嵌入 | 每张图片通过 PR_ATTACH_CONTENT_ID 协议正确嵌入 |
| CSS 兼容性 | `min-height:1px;visibility:visible!important` 防止 Outlook 拦截 |
| 按钮自适应 | 用 `QSizePolicy.Fixed` + `QFontMetrics` 计算宽度，解决溢出 |
| 版本号 | 标题栏显示 `V3.0.20260509` |
| 保存切图 | 新增「保存切图」按钮，可不发送邮件直接保存切片到本地 |
| PPT/PPTX 支持 | 新增 PPT/PPTX 幻灯片渲染为图片（PyMuPDF），每页独立切片插入 |

---

## 2. 功能规格

### 2.1 核心功能

#### F1: 图片拖入与识别
- **输入：** 用户将图片文件（PNG / JPG / JPEG / BMP / WebP / GIF）或 PDF / PPT / PPTX 文件拖入工具窗口
- **行为：**
  - 识别文件格式和尺寸
  - 若图片宽度 > 1728px，等比缩放至 1728px 宽
  - 若图片高度 > 1728px，标记为需要切片
  - 若图片宽高均 ≤ 1728px，直接推送插入 Outlook
  - PPT/PPTX：每张幻灯片渲染为一张图，若单页高度超 1728px 再次切片
- **输出：** 显示图片预览和切片方案（横向分片数 × 纵向分片数）

#### F2: 图像无损切片
- **触发条件：** 图片高度 > 1728px 或宽度 > 1728px
- **切片策略：**
  - 高度优先切片：先按 1728px 高度分片，剩余部分不足 1728px 时归入最后一片
  - 横向：若宽度 > 1728px，先将图片等比缩放到 1728px 宽，再按上述策略切片
  - 切片顺序：从上到下，从左到右，命名格式 `slice_001.png`, `slice_002.png`, ...
- **无损保证：** 使用 PNG 格式保存切片，保留完整颜色信息，无 JPEG 有损压缩
- **内存处理：** 使用 Pillow 的 `crop()` 逐片处理，不一次性加载整个大图到显存

#### F3: Outlook 邮件正文插入
- **接口：** 通过 pywin32 调用 COM 自动化 Outlook
- **流程：**
  1. 打开新邮件窗口 (`olMailItem`)
  2. 获取邮件正文编辑器对象 (`WordEditor`)
  3. 将切片图片逐张插入正文，图片之间无缝衔接（顶部对齐）
  4. 图片以 **嵌入式内联图片** 形式插入（非附件）
- **格式：** HTML 邮件格式，图片 src 使用 cid（Content-ID）嵌入

#### F4: 进度反馈
- 工具窗口底部显示操作进度条
- 状态文字实时更新：准备 → 切片中 → 插入中 → 完成
- 错误时红色提示并允许重试

#### F5: 快捷键
| 快捷键 | 功能 |
|---|---|
| `Ctrl+V` | 粘贴图片 |
| `Ctrl+O` | 打开文件选择对话框 |
| `Esc` | 关闭窗口 |

### 2.2 边界条件处理

| 场景 | 处理方式 |
|---|---|
| 图片宽高均 ≤ 1728px | 直接插入，不切片 |
| 图片高度恰好为 1728px 的整数倍 | 最后一片高度为 0 → 跳过最后一片 |
| 拖入非图片文件 | 显示错误提示"仅支持图片文件" |
| 图片尺寸获取失败 | 显示错误提示"无法读取图片" |
| Outlook 未安装 | 显示错误提示"未检测到 Outlook，请安装后重试" |
| Outlook 被其他窗口阻塞 | 等待最多 5 秒超时，超时则提示用户关闭其他 Outlook 窗口 |
| 图片切片数 > 20 | 提示"图片过长，可能需要较长时间插入，确认继续？" |
| 用户取消操作 | 重置状态，清理临时文件 |

---

## 3. 技术架构

### 3.1 模块划分

```
outlook-img-slicer/
├── main.py                 # 程序入口，PySide6 应用启动
├── ui/
│   ├── __init__.py
│   └── main_window.py      # 主窗口，拖放区域，状态栏
├── core/
│   ├── __init__.py
│   ├── image_slicer.py     # 图像切片逻辑（Pillow）
│   └── outlook_inserter.py # Outlook 插入逻辑（pywin32）
├── utils/
│   ├── __init__.py
│   └── file_utils.py       # 临时文件管理
├── assets/
│   └── icon.ico            # 程序图标
└── SPEC.md
```

### 3.2 技术架构图（文字描述）

```
┌─────────────────────────────────────────────────────┐
│                    UI 层 (PySide6)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  拖放区域    │  │  预览面板    │  │  状态栏   │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                  业务逻辑层 (core/)                  │
│  ┌──────────────────────┐  ┌───────────────────────┐ │
│  │   image_slicer.py    │  │  outlook_inserter.py  │ │
│  │  • 尺寸检测           │  │  • COM 初始化         │ │
│  │  • 缩放（宽>1728px） │  │  • 打开新邮件         │ │
│  │  • 高度切片           │  │  • WordEditor 插入图片 │ │
│  │  • PNG 无损保存       │  │  • HTML cid 嵌入      │ │
│  └──────────────────────┘  └───────────────────────┘ │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────┐
│                   依赖层 (Python Libs)               │
│  Pillow │ PyMuPDF (备选) │ pywin32 │ PySide6        │
└─────────────────────────────────────────────────────┘
```

### 3.3 数据流

```
用户拖入图片
    ↓
[UI] 接收文件路径 → 验证格式 → 获取尺寸
    ↓
[core/image_slicer] 判定是否需要切片
    ↓ (需要切片)
创建临时目录（temp/）
    ↓
Pillow.open() → 逐片 crop() → save(PNG) → slice_001.png ...
    ↓
[core/outlook_inserter] 初始化 pywin32 COM
    ↓
Outlook.Application() → .CreateItem(olMailItem)
    ↓
mail.GetInspector.WordEditor → 遍历切片插入 HTML <img src="cid:slice_N">
    ↓
显示完成状态
    ↓
清理临时目录
```

---

## 4. API / 接口设计

本工具为桌面应用，无 REST API。以下为内部模块接口：

### 4.1 `image_slicer.py`

```python
def slice_image(input_path: str, output_dir: str, max_height: int = 1728, max_width: int = 1728) -> list[str]:
    """
    对图片进行无损切片。

    参数:
        input_path:  输入图片路径
        output_dir:   切片输出目录
        max_height:   最大高度（默认1728）
        max_width:    最大宽度（默认1728）

    返回:
        切片文件路径列表，按插入顺序排列

    异常:
        ValueError: 图片格式不支持或文件损坏
    """
```

### 4.2 `outlook_inserter.py`

```python
def insert_images_to_outlook(image_paths: list[str], subject: str = "") -> bool:
    """
    将图片插入 Outlook 新邮件正文。

    参数:
        image_paths:  切片图片路径列表
        subject:      邮件主题（可选）

    返回:
        True 成功，False 失败
    """
```

---

## 5. 错误处理策略

| 错误类型 | 检测方式 | 用户提示 | 恢复策略 |
|---|---|---|---|
| 非图片文件 | 扩展名 + Pillow.open() 异常 | "仅支持图片格式：PNG/JPG/BMP/WebP/GIF" | 重置，等待重新拖入 |
| 图片读取失败 | IOError / Pillow 异常 | "无法读取图片，文件可能已损坏" | 重置 |
| Outlook 未安装 | pywin32 com exception | "未检测到 Microsoft Outlook，请安装后重试" | 退出或重试 |
| Outlook 被占用 | COM 超时（5s） | "Outlook 正被其他窗口占用，请关闭后重试" | 重置，等待手动操作 |
| 临时目录创建失败 | OSError | "无法创建临时目录，请检查磁盘空间" | 重置 |
| 切片保存失败 | IOError | "保存切片失败，请检查磁盘空间" | 清理已保存切片，重试 |
| Outlook 弹窗阻塞 | WordEditor 获取超时 | "Outlook 窗口被阻塞，请关闭所有弹窗" | 提示用户手动处理 |

---

## 6. 用户操作流程

```
步骤 1：启动工具
  → 显示主窗口，包含拖放提示区域："将图片拖入此处"

步骤 2：拖入图片
  → 显示图片预览
  → 显示切片方案（如：3 × 1，表示切成 3 片）

步骤 3：确认切片数量（>20片时）
  → 弹出确认对话框："图片将切成 N 片，继续？"
  → 用户确认或取消

步骤 4：点击"插入 Outlook"按钮（或 Ctrl+Enter）
  → 进度条开始工作
  → 状态："正在切片..."
  → 切片完成
  → 状态："正在插入 Outlook..."
  → 弹出 Outlook 新邮件窗口，图片已插入

步骤 5：完成
  → 状态："完成！共插入 N 张图片"
  → 进度条 100%
  → 工具窗口自动关闭（可选）或保持打开

异常流程：
  → 任何步骤出错 → 红色提示 → 重试按钮
  → 用户按 Esc → 取消操作 → 清理临时文件 → 重置窗口
```

---

## 7. 验收标准

### 7.1 功能验收

- [ ] 支持 PNG / JPG / JPEG / BMP / WebP / GIF 格式拖入
- [ ] 宽高均 ≤ 1728px 的图片直接插入，不切片
- [ ] 高度 > 1728px 的图片按每片 1728px 高度切片
- [ ] 宽度 > 1728px 的图片先等比缩放至 1728px 宽，再按高度切片
- [ ] 切片为 PNG 格式，无有损压缩
- [ ] 插入 Outlook 后，邮件正文显示完整长图，无截断
- [ ] 插入 Outlook 后，图片清晰度与原图一致
- [ ] 进度条实时反馈操作进度
- [ ] 快捷键 Ctrl+V 粘贴图片生效
- [ ] Esc 键关闭工具生效

### 7.2 错误处理验收

- [ ] 拖入非图片文件时，显示错误提示，不崩溃
- [ ] 未安装 Outlook 时，显示明确提示，不闪退
- [ ] Outlook 被其他窗口占用时，显示超时提示
- [ ] 操作取消后，临时文件正确清理

### 7.3 性能验收

- [ ] 单张图片切片过程 < 5 秒（图片面积 ≤ 50MP）
- [ ] 工具启动时间 < 3 秒
- [ ] 内存占用峰值 < 500MB（切片过程）

### 7.4 打包验收

- [ ] PyInstaller / Nuitka 打包为单文件 exe
- [ ] exe 在 Windows 10/11 纯净系统上可直接运行
- [ ] exe 文件图标正确显示

---

## 8. 技术选型理由

| 依赖 | 选型 | 理由 | 开源项目 |
|---|---|---|---|
| UI 框架 | PySide6 | LGPL 授权，官方维护，功能完整 | Qt (qt.io) |
| 图像处理 | Pillow 10+ | 切片/合并/压缩核心库 | python-pillow/Pillow ⭐13k |
| 图片压缩参考 | MozJPEG 算法 | 感知量化优化 JPEG 体积 | mozilla/mozjpeg ⭐2.8k |
| 图片拼接参考 | Pillow paste | 纵向居中拼接 | nkmk/python-snippets ⭐317 |
| PDF 解析 | PyMuPDF | 保留作为备选 | pymupdf/PyMuPDF |
| Outlook 自动化 | pywin32 | Windows COM 自动化 Outlook 的标准方案 | mhammond/pywin32 |
| 打包 | PyInstaller | --onefile 单文件 exe | pyinstaller/pyinstaller |

## 9. 参考的开源项目

| 项目 | GitHub | 用途 |
|------|--------|------|
| Pillow | https://github.com/python-pillow/Pillow | 所有图像处理（切片/合并/压缩/格式转换）|
| MozJPEG | https://github.com/mozilla/mozjpeg | JPEG 压缩量化表参考 |
| nkmk/python-snippets | https://github.com/nkmk/python-snippets | Pillow concat 拼接模式参考 |
| PyInstaller | https://github.com/pyinstaller/pyinstaller | 单文件 EXE 打包 |
| PySide6 | https://pypi.org/project/PySide6/ | Qt6 UI 框架 |
| PyMuPDF | https://github.com/pymupdf/PyMuPDF | PDF 渲染 |
| python-pptx | https://github.com/scanny/python-pptx | PPTX 幻灯片提取 |
