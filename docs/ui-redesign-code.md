# main.py 代码质量分析报告

**文件**: `/Users/huashu/outlook-img-slicer/main.py`
**行数**: 511 | **MD5**: `0c4a4de3a08fdb057d23e2d03f1527e6`
**版本**: V3.0.20260511-TEST

---

## 1. 重复代码

### 1.1 `_btn_style()` 方法重复调用模式（~6处）

`_btn_style()` 在 `_build_ui()` 中被反复调用，每次都传参生成新的样式字符串，但样式几乎一致。

```python
# 行 226-231
btn_select.setStyleSheet(self._btn_style(Theme.CARD, Theme.TEXT))
# 行 234-239
btn_reset.setStyleSheet(self._btn_style(Theme.CARD, Theme.SUBTEXT))
# 行 302-305（内联定义，无须调用）
self.btn_send.setStyleSheet(f"QPushButton {{ ... }}")
# 行 307-310
btn_save.setStyleSheet(self._btn_style(Theme.CARD, Theme.SUBTEXT))
```

**问题**: `btn_send` 的样式直接在 `setStyleSheet` 里写死，没有复用 `_btn_style()`，导致主题色变更时需改两处。

### 1.2 PDF / PPT 处理逻辑大量重复

```python
# 行 156-167（PDF）和 168-180（PPT）几乎完全一致
if ext == ".pdf":
    images = pdf_to_images(self.file_path)
    self.progress.emit(45)
    slice_paths = []
    temp_dir = tempfile.gettempdir()
    for index, image in enumerate(images):
        path = os.path.join(temp_dir, f"pdf_page_{index}.png")
        image.save(path)
        slice_paths.append(path)
elif ext in (".pptx", ".ppt"):
    images = pptx_to_images(self.file_path)
    self.progress.emit(45)
    slice_paths = []
    temp_dir = tempfile.gettempdir()
    for index, image in enumerate(images):
        path = os.path.join(temp_dir, f"ppt_page_{index}.png")
        image.save(path)
        slice_paths.append(path)
```

**重复代码约 15 行**，仅 `pdf_to_images` / `pptx_to_images` 和文件名模板不同。

### 1.3 状态标签样式设置重复

每次更新 `status_label` 都要写 `setStyleSheet(f"color: ...; font-size: 12px;")`：

- 行 265: `self.status_label.setStyleSheet(f"color: {Theme.SUBTEXT}; font-size: 12px;")`
- 行 286: `self.status_label.setStyleSheet(f"color: {Theme.SUBTEXT}; font-size: 12px;")`
- 行 297: `self.status_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 12px;")`
- 行 305: `self.status_label.setStyleSheet(f"color: {Theme.ERROR}; font-size: 12px;")`
- 行 394: `self.status_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 12px;")`

共 5 处，应抽取为 `set_status(text, level)` 方法。

---

## 2. 结构问题

### 2.1 QSS 样式分散，未集中管理

- `Theme` 类仅含颜色常量，**不含字体、间距、圆角、阴影等样式**
- `_btn_style()` 和 `_input_style()` 动态生成字符串，调试困难
- `DropZone._apply_style()` 用内联字符串硬编码样式
- 调试行 `debug_label` 也有自己的硬编码样式

**建议**: 引入 `QSSLoader` 或 `StylesheetManager` 类，所有 QSS 集中管理，支持一次性替换。

### 2.2 Theme 类扩展性不足

当前 `Theme` 只有颜色，没有：
- 字体定义（font family、font size 级别）
- 间距常量（spacing, margin, padding）
- 圆角/边框常量
- 阴影常量

---

## 3. 字体问题

### 3.1 字体大小使用混乱

| 元素 | 当前字体大小 | 问题 |
|------|-------------|------|
| Header | 18px Bold | 偏大 |
| 副标题 | 12px | 偏小，与 12px SUBTEXT 混用 |
| DropZone title | 13px Bold | 重复定义 |
| DropZone tip | 12px SUBTEXT | 无问题 |
| 按钮 | 13/14px | 无问题 |
| 调试行 | 10px | 与 footer version 11px 跳跃 |
| Footer version | 11px | 无问题 |

**问题**: 同一类元素（标题/正文）有多档字号，缺少层级定义。

### 3.2 `QFont("Microsoft YaHei", ...)` 硬编码重复

在 10+ 处硬编码字体 `QFont("Microsoft YaHei", size)`，一旦字体族改名（如改为系统默认）需全文件替换。

**建议**: `Theme.FONT_FAMILY = "Microsoft YaHei"`，所有 `QFont()` 调用统一引用。

---

## 4. 布局效率

### 4.1 多余的 `addStretch` 嵌套

```python
# 行 221
dbg_row.addWidget(debug_label)
dbg_row.addStretch()  # 仅为右对齐 debug_label

# 行 252
row1.addStretch()  # 右侧对齐 spin_width
```

正常用法，但 `bottom_row` 和 `version_row` 里也用 `addStretch` 做类似用途，无问题但略显冗余。

### 4.2 嵌套过深的 `QHBoxLayout`

`version_row` 只为放一个右对齐的 `ver_label`，可用 `setAlignment` 替代：
```python
# 当前
version_row = QHBoxLayout()
version_row.addStretch()
ver_label = QLabel(VERSION)
version_row.addWidget(ver_label)

# 可简化为
ver_label = QLabel(VERSION)
layout.addWidget(ver_label, alignment=Qt.AlignRight)
```

### 4.3 `preview_area` 用 `hide()/show()` 但 child widget 未清理

`_show_thumbnails` 里用 `deleteLater()` 清理旧缩略图，但 `preview_area` 的 widget 在 `hide()` 后仍然存在。

---

## 5. PySide6 最佳实践问题

### 5.1 `ProcessWorker` 线程结束后未清理

```python
# 行 268-271
self.worker = ProcessWorker(path, self.spin_width.value())
self.worker.progress.connect(self.progress_bar.setValue)
self.worker.finished.connect(self._on_processed)
self.worker.error.connect(self._on_error)
self.worker.start()
```

`worker` 完成后信号仍然连接，但 `worker` 本身没有 `deleteLater()` 或手动清理。若用户快速触发多次处理（连续选文件），可能产生多个 `QThread` 残留。

**建议**: 在 `_on_processed` / `_on_error` 中添加 `self.worker.deleteLater(); self.worker = None`。

### 5.2 `thumb_grid` 中的 `QLabel` 没有设置 `scaledContents=True`

```python
# 行 311-317
pixmap = QPixmap(path).scaled(120, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
thumb.setPixmap(pixmap)
```

`QLabel` 默认 `scaledContents=False`，在某些 Qt 版本下可能导致图片不居中。建议显式设置。

### 5.3 `QFileDialog.getOpenFileName` 编码问题

```python
path, _ = QFileDialog.getOpenFileName(...)  # 行 331
```

返回值 `path` 为 `str`，但在某些 Windows 环境（路径含非 ASCII）可能出问题。当前对中文路径处理没有显式处理。

---

## 6. 可优化点（5-10 个具体改进建议）

### 建议 1: 抽取 `_set_status()` 方法（行 283-305）
**位置**: `MainWindow` 类内
**改进**: 将 5 处 status 样式设置合并为：
```python
def _set_status(self, text: str, level: str = "info"):
    self.status_label.setText(text)
    colors = {"info": Theme.SUBTEXT, "success": Theme.SUCCESS, "error": Theme.ERROR}
    self.status_label.setStyleSheet(f"color: {colors.get(level, Theme.SUBTEXT)}; font-size: 12px;")
```
**影响**: 消除 5 处重复，修改时只需一处。

### 建议 2: PDF/PPT 公共逻辑提取（行 156-180）
**位置**: `ProcessWorker.run()`
**改进**: 抽取为 `_convert_to_images_and_slice()` 方法：
```python
def _convert_and_slice(self, converter_fn, prefix, progress_before, progress_after):
    images = converter_fn(self.file_path)
    self.progress.emit(progress_before)
    slice_paths = []
    temp_dir = tempfile.gettempdir()
    for index, image in enumerate(images):
        path = os.path.join(temp_dir, f"{prefix}_{index}.png")
        image.save(path)
        slice_paths.append(path)
    self.progress.emit(progress_after)
    return slice_paths
```
**影响**: 消除 ~15 行重复代码。

### 建议 3: 统一字体定义（Theme 类扩展）
**位置**: `Theme` 类，行 ~52
**改进**:
```python
class Theme:
    FONT_FAMILY = "Microsoft YaHei"
    FONT_SIZES = {"caption": 10, "small": 11, "body": 12, "subtitle": 13, "title": 18}
    # 替换全文件所有 QFont("Microsoft YaHei", X) 为 QFont(Theme.FONT_FAMILY, Theme.FONT_SIZES["X"])
```
**影响**: 14+ 处修改，但后续字体调整成本大幅降低。

### 建议 4: QSS 集中管理
**位置**: 新增 `QSSManager` 类或 `styles.qss` 文件
**改进**: 所有样式集中为常量字符串：
```python
QSS = {
    "btn_primary": f"QPushButton {{ background: {Theme.PRIMARY}; ... }}",
    "btn_secondary": f"QPushButton {{ background: {Theme.CARD}; ... }}",
    ...
}
```
**影响**: 调试友好，主题切换只需改一处。

### 建议 5: Worker 线程清理
**位置**: `_on_processed` 和 `_on_error`，行 ~293 和 ~300
**改进**:
```python
def _on_processed(self, paths: List[str]):
    self.slice_paths = paths
    self.progress_bar.hide()
    self.btn_send.setEnabled(bool(paths))
    self.btn_save.setEnabled(bool(paths))
    self.status_label.setText(f"已生成 {len(paths)} 张切片，准备发送")
    self._set_status(..., "success")
    self._show_thumbnails(paths)
    if self.worker:
        self.worker.deleteLater()
        self.worker = None
```
**影响**: 避免线程残留。

### 建议 6: `preview_area` widget 清理优化
**位置**: `_show_thumbnails` 行 ~309
**改进**: 在 `preview_area.hide()` 前显式清理，或使用 `QStackedWidget` 切换。

### 建议 7: `Config` 和 `Theme` 合并或建立关联
**位置**: 文件顶部类定义
**改进**: `Config` 中引用 `Theme` 颜色，避免硬编码字符串（如 `"#0078D4"` 在多处出现）。

### 建议 8: 按钮固定宽度逻辑统一为 `_apply_btn_fixed_size()`
**位置**: `MainWindow` 类
**改进**: `_btn_metric()` 已存在但未被所有按钮使用，`btn_send` 样式直接内联了 `setFixedSize`。统一为：
```python
def _apply_btn_size(self, btn: QPushButton, text: str, font_size: int = 13):
    btn.setFixedSize(_btn_metric(text, font_size))
    btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
```

### 建议 9: 调试行 `debug_label` 抽取为 `_build_debug_bar()`
**位置**: `_build_ui` 行 ~204
**改进**: 单独方法，上线时一行注释即可禁用，利于 CI/CD 环境区分。

### 建议 10: `_on_error` 异常信息本地化
**位置**: `_on_error` 行 ~300
**改进**: 将 `str(exc)` 包装为中文友好提示，避免暴露原始异常。

---

## 总结

| 维度 | 评分 | 主要问题 |
|------|------|---------|
| 重复代码 | ⚠️ 中 | PDF/PPT 逻辑、status 样式、QFont 硬编码 |
| 结构 | ⚠️ 中 | QSS 分散，Theme 不完整 |
| 字体 | ⚠️ 低-中 | 字号层级不清，字体族硬编码 |
| 布局效率 | ✅ 良 | 仅 minor 冗余 |
| PySide6 最佳实践 | ⚠️ 中 | worker 未清理、信号残留风险 |

---

*本报告基于静态代码分析，不包含运行时测试。建议优先处理建议 1、5、2（重复代码消除 + 线程清理），再进行 UX/PM 重构阶段。*
