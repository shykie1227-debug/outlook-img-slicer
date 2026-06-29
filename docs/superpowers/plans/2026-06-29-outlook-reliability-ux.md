# Outlook Reliability and UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复经典 Outlook 长图热区不完整、复制 HTML 截断和布局错位，并改善桌面工具的默认操作体验。

**Architecture:** 保留普通 V3 图片堆叠与 CID 邮件主链路。热区切片改为逐视觉行最小分段，HTML 使用彼此独立的 inline 行；剪贴板封装独立为可测试的 UTF-8 字节偏移逻辑。

**Tech Stack:** Python 3.10+, PySide6, Pillow, pywin32, pytest, PyInstaller

## Global Constraints

- 最终 EXE 100% 离线，无网络依赖、无云 API、无上传。
- Outlook 只允许 `mail.Display(False)`，禁止 `mail.Send()`。
- 普通无热区长图保持 V3 连续 `<img>` 结构。
- Windows 经典 Outlook 是主要邮件目标。
- 所有行为变更先观察失败测试，再写最小实现。
- 不覆盖无关的现有工作区改动。

---

### Task 1: 修复 Windows CF_HTML UTF-8 偏移

**Files:**
- Create: `clipboard_html.py`
- Modify: `main.py`
- Test: `tests/test_clipboard_html.py`

**Interfaces:**
- Produces: `build_windows_clipboard_html(html: str) -> bytes`
- Produces: `extract_html_fragment(html: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
def test_cf_html_offsets_use_utf8_bytes_for_chinese():
    payload = build_windows_clipboard_html("<html><body><p>按钮中文测试</p></body></html>")
    offsets = parse_offsets(payload)
    assert payload[offsets["EndFragment"]:].startswith(b"<!--EndFragment-->")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_clipboard_html.py -q`
Expected: FAIL because `EndFragment` points inside the UTF-8 Chinese text.

- [ ] **Step 3: Write minimal implementation**

```python
prefix = "<html><body><!--StartFragment-->"
suffix = "<!--EndFragment--></body></html>"
body_bytes = (prefix + fragment + suffix).encode("utf-8")
start_fragment = start_html + len(prefix.encode("utf-8"))
end_fragment = start_fragment + len(fragment.encode("utf-8"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_clipboard_html.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add clipboard_html.py main.py tests/test_clipboard_html.py
git commit -m "fix: use byte-correct Outlook clipboard offsets"
```

### Task 2: 最小化热区物理切片

**Files:**
- Modify: `hotspot_slicer.py`
- Test: `tests/test_hotspot_minimal_partition.py`

**Interfaces:**
- Consumes: `Hotspot`
- Produces: `slice_image_with_hotspots(img, hotspots, source_index) -> list[CutStripe]`

- [ ] **Step 1: Write the failing test**

```python
def test_two_staggered_buttons_create_nine_pieces_not_global_grid():
    stripes = slice_image_with_hotspots(image, [top_left, bottom_right], 1.0)
    assert len(stripes) == 9
    assert sum(s.href is not None for s in stripes) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_hotspot_minimal_partition.py -q`
Expected: FAIL with 25 pieces from the current global X/Y grid.

- [ ] **Step 3: Write minimal implementation**

```python
for row, (y1, y2) in enumerate(pairwise(y_lines)):
    active = [h for h in hotspots if h.y1 <= y1 and h.y2 >= y2]
    x_lines = sorted({0, img_w, *(x for h in active for x in (h.x1, h.x2))})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_hotspot_minimal_partition.py -q`
Expected: PASS with preserved pixel area and two linked segments.

- [ ] **Step 5: Commit**

```bash
git add hotspot_slicer.py tests/test_hotspot_minimal_partition.py
git commit -m "fix: minimize clickable hotspot image partitions"
```

### Task 3: 恢复 Outlook 独立热区行

**Files:**
- Modify: `html_assembler.py`
- Modify: `tests/test_v4811_hotspot_grid_v2.py`
- Modify: `tests/test_v481_generate_plain_html_materialize.py`
- Test: `tests/test_outlook_hotspot_layout.py`

**Interfaces:**
- Produces: `_build_inline_segment(...) -> str`
- Produces: `_build_complex_inline_stack(...) -> tuple[str, int]`

- [ ] **Step 1: Write the failing test**

```python
def test_hotspot_rows_do_not_share_table_columns(prepared_items):
    html = assemble_html(prepared_items, 650)
    assert html.count("<table") == 1
    assert html.count("<div") == len(_group_by_source(prepared_items))
    assert "display: inline-block" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_outlook_hotspot_layout.py -q`
Expected: FAIL because current working tree emits one nested table per row.

- [ ] **Step 3: Write minimal implementation**

```python
row = (
    f'<div style="display:block;width:{row_width}px;height:{row_height}px;'
    'font-size:0;line-height:0;white-space:nowrap">'
    f"{segments}</div>"
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_outlook_hotspot_layout.py tests/test_v4811_hotspot_grid_v2.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add html_assembler.py tests/test_outlook_hotspot_layout.py tests/test_v4811_hotspot_grid_v2.py tests/test_v481_generate_plain_html_materialize.py
git commit -m "fix: isolate Outlook hotspot rows"
```

### Task 4: 增加手动切线编辑与防呆

**Files:**
- Create: `cut_editor.py`
- Modify: `main.py`
- Test: `tests/test_manual_cut_editor.py`

**Interfaces:**
- Produces: `validate_cut_positions(total_height, cut_positions, min_height=80, max_height=1200) -> list[int]`
- Produces: `reslice_existing_stack(slice_paths, cut_positions) -> list[str]`
- Produces: `CutEditorDialog(slice_paths, max_slice_height, parent=None)`

- [ ] **Step 1: Write the failing test**

```python
def test_manual_cut_positions_preserve_all_pixels(tmp_path):
    paths = reslice_existing_stack(source_slices, [500, 1200])
    assert image_heights(paths) == [500, 700, 600]
    assert vertical_pixels(paths) == vertical_pixels(source_slices)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_manual_cut_editor.py -q`
Expected: FAIL because the manual cut model and dialog do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
boundaries = [0, *validate_cut_positions(total_height, cut_positions), total_height]
for top, bottom in pairwise(boundaries):
    combined.crop((0, top, combined.width, bottom)).save(target, "PNG")
```

The dialog uses a scrollable full-image preview with draggable horizontal cut lines, exact pixel labels, “恢复自动切线”, Cancel and Apply. Moving a line is clamped so adjacent slices stay between 80px and 1200px.

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_manual_cut_editor.py tests/test_main_window_ux.py -q`
Expected: PASS; the button is disabled before processing and enabled after slices exist.

- [ ] **Step 5: Commit**

```bash
git add cut_editor.py main.py tests/test_manual_cut_editor.py tests/test_main_window_ux.py
git commit -m "feat: add guarded manual cut editor"
```

### Task 5: 优化主窗口操作体验

**Files:**
- Modify: `main.py`
- Test: `tests/test_main_window_ux.py`

**Interfaces:**
- Consumes: `Config`, `Theme`, `MainWindow`
- Produces: `MainWindow._format_status_text(text, level) -> str`

- [ ] **Step 1: Write the failing test**

```python
def test_classic_outlook_defaults_are_clear(qapp):
    win = MainWindow()
    assert win.edit_width.text() == "650"
    assert win.chk_smart.text() == "避开文字切图（推荐）"
    assert win.btn_send.text() == "在经典 Outlook 中创建邮件"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_main_window_ux.py -q`
Expected: FAIL on the current 960px default and older labels.

- [ ] **Step 3: Write minimal implementation**

```python
class Config:
    DEFAULT_WIDTH = 650

def _format_status_text(text, level):
    clean = text.lstrip("ℹ️✅❌⚠️ ").strip()
    return f"{icons.get(level, '')} {clean}".strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_main_window_ux.py -q`
Expected: PASS with no duplicated status icon.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_main_window_ux.py
git commit -m "feat: clarify classic Outlook workflow"
```

### Task 6: 版本、文档和完整验证

**Files:**
- Modify: `main.py`
- Modify: `version_info.txt`
- Modify: `README.md`
- Modify: `SPEC.md`
- Test: `tests/test_release_consistency.py`

**Interfaces:**
- Produces: synchronized `5.0.0` application and Windows file version.

- [ ] **Step 1: Write the failing test**

```python
def test_release_version_is_synchronized():
    assert main.VERSION == "5.0.0"
    assert "5.0.0.20260629" in VERSION_INFO
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_release_consistency.py -q`
Expected: FAIL on version 4.9.5.

- [ ] **Step 3: Update version and user documentation**

```python
VERSION = "5.0.0"
```

Document the classic Outlook requirement, 650px recommended width, hotspot behavior, copy-HTML fallback and manual `python build.py` flow.

- [ ] **Step 4: Run complete verification**

Run:

```bash
python3 -m py_compile *.py
QT_QPA_PLATFORM=offscreen python3 -m pytest -q
```

Expected: all tests pass and compilation exits 0.

- [ ] **Step 5: Commit**

```bash
git add main.py version_info.txt README.md SPEC.md tests/test_release_consistency.py DESIGN.md docs/superpowers
git commit -m "release: prepare Outlook image slicer 5.0.0"
```
