# UI 优化后测试计划 — Outlook 长图无损插入工具 V3

> **测试工程师：** AI Subagent
> **测试日期：** 2026-05-09
> **测试版本：** V3.0.20260511-TEST
> **覆盖模块：**
> - `image_slicer.py`（图像切片）
> - `html_assembler.py`（HTML 组装）
> - `pdf_slicer.py`（PDF 渲染）
> - `ppt_slicer.py`（PPT 渲染）
> - `main.py`（PySide6 主窗口 UI）
> - `outlook_sender.py`（Outlook 发送）

---

## 一、测试范围说明

本次测试基于 SPEC.md 中 V3 版本的改进清单，重点覆盖：

1. **UI 交互流程**（拖拽 → 预览 → 切片 → 发送）
2. **核心切片逻辑**（高度边界、宽度缩放、ceil 公式验证）
3. **边界条件**（不支持格式、损坏文件、切片数超限）
4. **PPT/PDF 多页处理**

---

## 二、核心功能测试用例

### 2.1 图像切片逻辑（`image_slicer.py`）

| 用例编号 | 场景 | 输入 | 操作 | 预期结果 |
|---|---|---|---|---|
| `TC-IMG-001` | 宽高均 ≤ 1728px | 800×1200 PNG | `detect_and_slice(path, max_height=1728)` | 返回 `[path]`（原路径），不切片 |
| `TC-IMG-002` | 高度 > 1728px | 800×3000 PNG | `detect_and_slice(path, max_height=1728)` | 返回 2 张切片，`ceil(3000/1728)=2` |
| `TC-IMG-003` | 高度恰好是 1728px 整数倍 | 800×3456 PNG | `detect_and_slice(path, max_height=1728)` | `slice_count = ceil(3456/1728)=2`，最后一片 top=1728 bottom=3456（高度 1728），无 0 高度片 |
| `TC-IMG-004` | 高度 1px 超过阈值 | 800×1729 PNG | `detect_and_slice(path, max_height=1728)` | `ceil(1729/1728)=2`，生成 2 张切片 |
| `TC-IMG-005` | 宽度 > 1728px，高度正常 | 2000×1200 PNG | `detect_and_slice(path, max_height=1728)` | **注意：** 当前实现**未处理宽度缩放**，仅按 max_height 切片。需确认是否需要等比缩放至 1728px 宽（见 SPEC.md F2 横向策略） |
| `TC-IMG-006` | 多格式支持 | 600×2000 BMP | `detect_and_slice(path)` | 切片生成，格式正确 |
| `TC-IMG-007` | 多格式支持 | 600×2000 WebP | `detect_and_slice(path)` | 切片生成，格式正确 |
| `TC-IMG-008` | 多格式支持 | 600×2000 GIF | `detect_and_slice(path)` | 切片生成，格式正确 |
| `TC-IMG-009` | PNG 透明通道保留 | 800×3000 RGBA PNG | `detect_and_slice(path)` | 输出图片 mode=RGBA，alpha 通道保留 |
| `TC-IMG-010` | JPEG 透明处理 | 800×3000 RGB JPEG | `detect_and_slice(path)` | 切片保存为 JPEG quality=95，非 RGBA 混入 |
| `TC-IMG-011` | 切片命名格式 | 800×3000 PNG | `detect_and_slice(path)` | 文件名格式：`slice_0_<stem>.png`, `slice_1_<stem>.png` |
| `TC-IMG-012` | 损坏图片文件 | `.txt` 伪装成 `.png` | `detect_and_slice(path)` | 抛出异常，信息包含"图片切片失败" |

---

### 2.2 HTML 组装逻辑（`html_assembler.py`）

| 用例编号 | 场景 | 输入 | 预期结果 |
|---|---|---|---|
| `TC-HTML-001` | 空图片列表 | `assemble_html([], 800)` | 表格结构完整，无 `cid:` 出现 |
| `TC-HTML-002` | 单张图片 | `assemble_html([path], 800)` | 一个 `<img src="cid:slice_001">` |
| `TC-HTML-003` | 多张图片 | `[path1, path2, path3]` | 三个 `<img src="cid:slice_00N">`，N 从 001 递增 |
| `TC-HTML-004` | CID 映射 | `get_cid_map([p1, p2])` | 返回 `{0: "slice_001", 1: "slice_002"}` |
| `TC-HTML-005` | 自定义宽度 | `assemble_html([path], 650)` | HTML 中 `width: 650px` |
| `TC-HTML-006` | Outlook 表格兼容性 | 生成的 HTML | 使用 `<table>` 结构，`margin: 0 auto`，`text-align: center` |

---

### 2.3 PDF 处理（`pdf_slicer.py`）

| 用例编号 | 场景 | 预期结果 |
|---|---|---|
| `TC-PDF-001` | 单页 PDF | 生成 1 张 PIL Image |
| `TC-PDF-002` | 多页 PDF（如 5 页） | 生成 5 张 PIL Image，每页独立 |
| `TC-PDF-003` | 不存在的 PDF 路径 | 抛出 `RuntimeError("PDF 解析失败")` |
| `TC-PDF-004` | PDF 渲染 DPI 参数 | `dpi=150` 参数存在且生效 |

---

### 2.4 PPT 处理（`ppt_slicer.py`）

| 用例编号 | 场景 | 预期结果 |
|---|---|---|
| `TC-PPT-001` | 单页 PPTX | 生成 1 张 PIL Image |
| `TC-PPT-002` | 多页 PPTX（如 10 页） | 生成 10 张 PIL Image，每页独立 |
| `TC-PPT-003` | 不存在的 PPTX 路径 | 抛出 `RuntimeError("PPT 渲染失败")` |
| `TC-PPT-004` | 页面高度 > 1728px（需二次切片） | `main.py` 中 `ProcessWorker` 调用 `detect_and_slice`，生成多张切片 |
| `TC-PPT-005` | PPT 渲染 DPI | `dpi=150` 参数存在且生效 |

---

## 三、UI 交互测试用例

### 3.1 拖拽与文件选择

| 用例编号 | 场景 | 操作 | 预期结果 |
|---|---|---|---|
| `TC-UI-001` | 拖入支持的图片 | 拖入 `test.png` | `DropZone` 图标变 ✅，`title_label` 显示文件名 |
| `TC-UI-002` | 拖入 PDF | 拖入 `test.pdf` | 同上，文件类型被识别 |
| `TC-UI-003` | 拖入 PPTX | 拖入 `test.pptx` | 同上 |
| `TC-UI-004` | 拖入不支持格式 | 拖入 `test.txt` | 弹出 `QMessageBox.warning("格式不支持")` |
| `TC-UI-005` | 点击 DropZone | 单击 | 打开文件选择对话框 |
| `TC-UI-006` | Ctrl+V 粘贴 | 在窗口内按 `Ctrl+V` | **注意：** 当前 `main.py` 未实现 `Ctrl+V` 处理（SPEC.md F5 有要求），需验证是否缺失 |

---

### 3.2 Row1 按钮状态

| 用例编号 | 场景 | 操作→预期结果 |
|---|---|
| `TC-UI-007` | 初始状态 | **「选择文件」** 和 **「重置」** 按钮可见，`btn_send` 和 `btn_save` 为 `disabled` |
| `TC-UI-008` | 文件选中后 | `btn_send` 和 `btn_save` 变为 `enabled` |
| `TC-UI-009` | 点击「重置」 | 所有状态恢复初始，`slice_paths` 清空，按钮恢复 `disabled` |

---

### 3.3 进度反馈

| 用例编号 | 场景 | 预期行为 |
|---|---|---|
| `TC-UI-010` | 文件拖入后 | `progress_bar` 显示，`status_label` 变为"正在处理，请稍候..." |
| `TC-UI-011` | 处理完成后（切片） | `progress_bar` 消失，`status_label` 绿色文字"已生成 N 张切片，准备发送" |
| `TC-UI-012` | 处理失败 | `progress_bar` 消失，`status_label` 红色文字显示错误信息，弹出 `QMessageBox.critical` |
| `TC-UI-013` | 进度值传递 | `ProcessWorker.progress.emit(15/45/75/100)` 信号正确驱动 `progress_bar.setValue` |

---

### 3.4 预览区域

| 用例编号 | 场景 | 预期结果 |
|---|---|---|
| `TC-UI-014` | 切片生成后 | `preview_area` 显示（`show()`），缩略图网格（4 列）正确排列 |
| `TC-UI-015` | 重置后 | `preview_area` 隐藏（`hide()`） |

---

### 3.5 邮件发送与保存

| 用例编号 | 场景 | 操作 | 预期结果 |
|---|---|---|---|
| `TC-UI-016` | `btn_send` 点击 | 调用 `create_email_with_images`，弹出 Outlook 邮件窗口 | `status_label` 显示"✅ 邮件窗口已打开，请检查后发送" |
| `TC-UI-017` | `btn_save` 点击 | 弹出目录选择对话框，保存切片 | `QMessageBox.information` 显示保存成功 |
| `TC-UI-018` | `to` 和 `subject` 字段 | 输入收件人和标题 | 传递给 `create_email_with_images` |

---

### 3.6 快捷键（SPEC.md F5）

| 用例编号 | 快捷键 | 预期功能 |
|---|---|---|
| `TC-UI-019` | `Ctrl+V` | 粘贴图片（**需验证 main.py 是否实现**） |
| `TC-UI-020` | `Ctrl+O` | 打开文件选择对话框（**需验证**） |
| `TC-UI-021` | `Esc` | 关闭窗口（**需验证**） |

---

## 四、边界条件测试

| 用例编号 | 场景 | 操作 | 预期结果 |
|---|---|---|---|
| `TC-BOUND-001` | 不支持文件格式 | 拖入 `.txt` / `.doc` | `QMessageBox.warning("格式不支持")` |
| `TC-BOUND-002` | 损坏的图片文件 | 传入内容损坏的图片 | 抛出异常，`status_label` 显示错误，不崩溃 |
| `TC-BOUND-003` | 切片数 > 20 | 拖入高度极大的图片（如 40000px） | `ceil(40000/1728)=24` > 20，**SPEC.md 要求弹出确认对话框**，当前 `main.py` 中未实现此检查 |
| `TC-BOUND-004` | Outlook 未安装 | 调用 `outlook_sender` | 显示"未检测到 Microsoft Outlook" |
| `TC-BOUND-005` | 空 PPTX 文件 | 渲染空 PPT | `RuntimeError("PPT 文件为空")` |

---

## 五、已知问题记录（测试前需确认）

> 以下为代码审查中发现的可疑点，测试时需重点验证：

1. **宽度 > 1728px 处理缺失**：`image_slicer.py` 的 `detect_and_slice` 仅按 `max_height` 切片，未实现 SPEC.md F2 中"宽度 > 1728px 时先等比缩放至 1728px 宽"的策略。此为功能缺口。

2. **切片数 > 20 无确认**：`main.py` 的 `ProcessWorker.run` 中未检查切片数量并弹出确认框，与 SPEC.md 边界条件处理表不符。

3. **快捷键未实现**：`main.py` 未注册 `Ctrl+V`、`Ctrl+O`、`Esc` 快捷键，与 SPEC.md F5 不符。

4. **PDF/PPT 渲染后无预览**：`ProcessWorker` 处理完成后直接 `finished.emit`，但 PDF/PPT 每页渲染后是独立的 `PIL Image`，再经 `detect_and_slice` 切片，最终切片路径列表传给 `_on_processed`，逻辑正确。

---

## 六、测试结果反馈模板

```markdown
## 测试反馈

- **测试人**：__________
- **测试日期**：__________
- **测试版本**：V3.0.20260511-TEST

### 通过的用例

| 用例编号 | 结果 | 备注 |
|---|---|---|
| TC-IMG-001 | ✅ PASS | |
| ... | ... | |

### 失败的用例

| 用例编号 | 结果 | 实际行为 | 期望行为 | 严重程度 |
|---|---|---|---|---|
| TC-IMG-005 | ❌ FAIL | 未缩放宽度 | 应先将宽度缩放至 1728px | Critical |
| ... | ... | ... | ... | |

### 发现的 Bug 列表

| Bug 编号 | 描述 | 严重程度 | 修复优先级 |
|---|---|---|---|
| BUG-001 | 宽度 > 1728px 时未进行等比缩放 | Critical | 高 |
| BUG-002 | 切片数 > 20 时未弹出确认框 | Major | 高 |
| BUG-003 | Ctrl+V 快捷键未实现 | Minor | 中 |

### 建议修复顺序

1. [高] BUG-001 — 宽度缩放逻辑
2. [高] BUG-002 — 切片数量确认
3. [中] BUG-003 — 快捷键注册

### 备注

- ...
```

---

## 七、执行检查清单

```
□ TC-IMG-001 ~ TC-IMG-012   （image_slicer 核心逻辑）
□ TC-HTML-001 ~ TC-HTML-006 （html_assembler）
□ TC-PDF-001 ~ TC-PDF-004   （pdf_slicer）
□ TC-PPT-001 ~ TC-PPT-005   （ppt_slicer）
□ TC-UI-001  ~ TC-UI-021    （UI 交互）
□ TC-BOUND-001 ~ TC-BOUND-005（边界条件）
□ 已知问题重点验证（宽度缩放、切片数确认、快捷键）
□ 填写测试反馈模板
```

---

*测试计划版本：v1.0 | 生成时间：2026-05-09*