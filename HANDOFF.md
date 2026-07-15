# HANDOFF — Outlook 长图助手 V6.3.0

> 交接日期：2026-07-15
> 当前版本：V6.3.0
> 测试状态：166 passed, 0 failed

---

## 1. 项目概述

PySide6 桌面工具，将长图/PDF/PPT 切片后插入 Outlook 邮件，保持原始清晰度。支持热区链接、智能切图、图片导出。

- 架构：`PySide6 桌面界面 + Python 图像处理 + Outlook COM`
- 构建：PyInstaller → `OutlookImgSlicer-V6.3.0.exe`
- 平台：Windows 10/11，经典 Outlook

## 2. 当前 UI 状态

### 布局结构（3 步分区）

```
[标题栏 40px — Outlook 长图助手 V6.3.0]
[应用标题 18px + 副标题 11px]
[引导药丸 10px：1 放入文件 → 2 调整切线/添加链接 → 3 创建邮件]

[Step 1: 放入文件]
  ├─ 拖放区（56px 黄色文件夹图标 + 标题 14px + 提示 11px）
  └─ 工具栏行(HBoxLayout)：
       [重置(32px)] [邮件宽度：960 px] │ [导出图片] [避开文字切图（推荐）] [stretch]

[Step 2: 编辑切片与链接]
  └─ [复制图片（兼容方式）] [调整切图位置] [添加可点击按钮]

[Step 3: 检查并输出]
  ├─ 邮件标题输入框(36px)
  ├─ 邮件品质下拉(30px)
  ├─ 状态提示(11px)
  └─ [在 Outlook 中创建邮件(Primary 42px)] [保存切图(Secondary 42px)]

[版本号 V6.3.0 + 作者]
```

### 精确尺寸规范

| 类型 | 高度 | 字号 | 图标 | 字重 | 圆角 |
|------|------|------|------|------|------|
| Primary | 42px | 13px | 18px 白色 | 700 | 21px |
| Secondary | 42px | 12px | 16px 深色 | 500 | 21px |
| Ghost | 32px | 11px | 16px 深色 | 400 | 16px |
| 拖放区图标 | — | — | 56px | — | — |

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+O | 选择文件 |
| Ctrl+V | 粘贴图片 |
| Ctrl+Enter | 创建 Outlook 邮件 |
| Esc | 重置（有切片时弹确认） |

### 复选框

| 复选框 | 默认 | 图标 | 功能 |
|--------|------|------|------|
| 导出图片 | 关闭 | image.svg 16px | 切图模式 ↔ 导出模式 |
| 避开文字切图（推荐） | 开启 | 无 | 智能避开文字区域 |

## 3. 图标规范

- 目录：`icons/`，共 13 个 SVG
- viewBox：24x24，彩色 stroke/fill（无圆形底座）
- 禁止：`currentColor`、`opacity`、`linearGradient`、`feDropShadow`
- 白色变体：`stroke="#ffffff"`（用于 Primary 蓝底按钮）
- 文件夹类：黄色拟物（`#f6c744` 主体 + `#e5a800` 翻盖）

## 4. 关键文件

| 文件 | 用途 |
|------|------|
| `desktop/main.py` | 主窗口 UI + 业务逻辑（~1600 行） |
| `desktop/ui-preview.html` | 浏览器 1:1 预览（修改 main.py 布局时必须同步） |
| `desktop/cut_editor.py` | 切图位置编辑器 |
| `desktop/hotspot_editor.py` | 热区链接编辑器 |
| `desktop/export_dialog.py` | 图片导出格式选择弹窗 |
| `desktop/export_worker.py` | 后台渲染、合并与写盘任务 |
| `desktop/ui_scaling.py` | 主编辑弹窗统一响应式缩放 |
| `desktop/version_info.txt` | Windows 版本信息 |
| `icons/*.svg` | 13 个彩色填充图标 |
| `image_slicer.py` | 图像切片核心 |
| `outlook_sender.py` | Outlook COM 邮件创建 |
| `build.py` | PyInstaller 构建入口 |

## 5. 版本号与发布信息同步

版本源和可执行文件属性必须同时更新：

1. `desktop/main.py` → `VERSION = "x.y.z"`
2. `desktop/version_info.txt` → `FileVersion` / `ProductVersion`
3. `desktop/ui-preview.html` → `<title>` 和 `.app-title`

随后运行 `tests/test_release_consistency.py` 与
`tests/test_documentation_release_contract.py`，确认 README、SPEC、CHANGELOG、
构建脚本和发布文件名没有遗留旧版本。

## 6. 测试

```bash
python3 -m pytest tests/ -q          # 166 passed
python3 -m compileall -q desktop     # 编译检查
```

## 7. 构建

```bash
python3 build.py                    # 默认内部产物 desktop/dist/OutlookImgSlicer.exe
```

若旧目录因 Windows/共享文件锁无法清理，内部产物会写入时间戳备用目录；
真实路径始终以根目录 `build-manifest.json` 为准。清单记录内部产物的路径、版本、
大小、SHA-256 和完整源码提交 SHA。Windows 包装脚本或 VM 构建完成后，按清单复制为最终发布文件：
`dist/OutlookImgSlicer-V6.3.0.exe`。文件名保持英文 ASCII。

## 8. 本轮（V6.3.0）修改摘要

- 切线编辑解除 1200px 拖动锁定，保留用户切线并自动补充 Outlook 安全切线。
- 热区图片只做一次整图缩放，所有行高总和严格等于唯一目标总高。
- 热区视觉行使用独立列网格，避免经典 Outlook 对不同 X 边界跨行重排。
- 复制图片增加全宽居中容器，Windows 使用原生 CF_HTML 剪贴板格式。
- 主窗口与三个编辑弹窗统一缩放字体、图标、控件尺寸、圆角、内边距和布局间距。
- 字体启用抗锯齿质量策略，Windows 优先 Microsoft YaHei UI。
- 导出渲染、合并和写盘在后台线程运行，显示阶段进度并真实应用 JPG 品质设置。

## 9. 后续优化空间

| 问题 | 优先级 | 建议 |
|------|--------|------|
| 多图拖入切图模式只处理第一张 + 模态弹窗 | 中 | 改为自动合并或内联选择 |
| _on_error 同时状态栏 + 模态弹窗 | 低 | 轻微错误只更新状态栏 |
| _save_slices 无进度反馈 | 中 | 添加进度条或计数 |
| 缩略图固定 128x130 | 低 | 根据 available_width 动态计算 |
| DropZone 拖入无平滑动画 | 低 | 添加 QPropertyAnimation |

## 10. 文档索引

| 文档 | 用途 |
|------|------|
| `DESIGN.md` | 设计规范（色值/字号/按钮/图标/布局/尺寸） |
| `CODE-AGENT-GUIDE.md` | 代码规范（文件结构/主题/按钮/图标/检查清单/布局） |
| `CODE-AGENT-PROMPT.md` | AI 编码 agent prompt 模板 |
| `SPEC.md` | 产品规格说明 |
| `CHANGELOG.md` | 版本变更记录 |
| `LOCAL_RULES.md` | 本地规则 |
| `TEST_PLAN.md` | 测试计划 |
| `AGENTS.md` / `CLAUDE.md` | 工作规范（用户画像/需求理解流程） |
| `HANDOFF.md` | 本文件 |
