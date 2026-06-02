# Bug 4：HTML 横向拼接消除"碎片化"

> V4.6.9 修复（真正根因） · 严重程度：**高** · 涉及文件：`html_assembler.py`

---

## 现象（用户报告）

> "添加可点击按钮依发送到 outlook 依旧是很多碎片错乱"
> "切图后选择编辑热区插入链接发送到 outlook 不能点击跳转，编辑热区后的切片变成多个碎片了"

V4.6.9 之前 V4.6.6-Bug 3 都修了，但用户装上 V4.6.9 仍报"碎片错乱"——**之前修的不是根本原因**。

## gstack 5 步调查

### Step 1：打印 hotspot_slicer 最终产物

```python
# 场景：1 张原图 1000×500 + 1 个 hotspot (400, 100) → (600, 400)
sim = {'long.png': [Hotspot(400, 100, 600, 400, 'https://test.com', source_index=1.0)]}
sk, lm = slice_paths_by_hotspots([p], sim, source_index_map={'long.png': 1.0})
```

| path | sort_key | width | height | href |
|------|----------|-------|--------|------|
| hs_001.png | 1.001 | 400 | 500 | None |
| hs_002.png | 1.002 | 200 | 500 | https://test.com |
| hs_003.png | 1.003 | 400 | 500 | None |

✅ 切割正确，sort_key 严格递增

### Step 2：拼接顺序

按 sort_key 排序：hs_001 → hs_002 → hs_003

拼接图（预期）：
```
┌──────────┬────────┬──────────┐
│ hs_001   │ hs_002 │ hs_003   │
│ 400x500  │200x500 │ 400x500  │
│ (普通)   │(链接)  │ (普通)   │
└──────────┴────────┴──────────┘
```

### Step 3：验证宽高总和 = 原图

| 项 | 值 |
|----|-----|
| 段数 | 3 |
| 总宽 | 400+200+400 = 1000 ✓ |
| 各高 | 500, 500, 500 ✓ 一致 |

✅ 切割层完全正确

### Step 4：HTML 实际结构（**根因命中**）

```python
trs = re.findall(r'<tr>.*?</tr>', html, re.S)
# 输出：3 个 <tr>
# 每个 <tr> 内 <td> 数量 = [1, 1, 1]
```

**实际 HTML**：
```html
<tr><td><img width="260"></td></tr>   ← 第 1 张图（行 1）
<tr><td><a><img width="130"></a></td></tr>  ← 第 2 张图（行 2）
<tr><td><img width="260"></td></tr>   ← 第 3 张图（行 3）
```

3 个 `<tr>` 纵向堆叠 = 3 张图垂直排列 = **1500px 高**（不是 500px）

**正确应该是**：
```html
<tr>
  <td><img width="260"></td>          ← 左段
  <td><a><img width="130"></a></td>   ← 中段（链接）
  <td><img width="260"></td>          ← 右段
</tr>
```

1 个 `<tr>` 3 个 `<td>` 横向 = 650px 宽 × 500px 高 = 完整原图

### Step 5：根因

**V1 物理切割产物**（每段 `y1=0, y2=H` 整高竖条）在 HTML 输出层**每段独占 1 个 `<tr>`** → 纵向堆叠。

V1 设计要求"竖条整高"（链接竖条整条可点）是对的，但 HTML 层没把"同一原图的多个竖条横向拼成 1 行"——错误。

## 修复

### 拆 `_build_image_row` 为 `_build_cell`

```python
# html_assembler.py
def _build_cell(slice_path, cid_or_src, display_w, href=None, alt="",
                original_width=0, is_base64=False):
    """只生成 <td>...</td>，不带 <tr>"""
    actual_w, actual_h = _get_img_dimensions(slice_path)
    if original_width > 0 and actual_w > 0:
        ratio = actual_w / original_width
        seg_display_w = round(display_w * ratio)
    else:
        seg_display_w = display_w
    seg_display_h = round(actual_h * seg_display_w / actual_w) if actual_w else 650

    # ... 构造 img_tag + a 包裹
    return f'<td align="left" valign="top" style="...">{inner}</td>\n'
```

### 新增 `_group_by_source()`：按 source_index 分组

```python
def _group_by_source(slices):
    sorted_slices = sorted(slices, key=lambda s: s.sort_key)
    groups = []
    current_group = []
    current_source = None
    for s in sorted_slices:
        src_idx = int(s.sort_key)  # 1.001 → 1
        if current_source is None or src_idx != current_source:
            if current_group:
                groups.append(current_group)
            current_group = [s]
            current_source = src_idx
        else:
            current_group.append(s)
    if current_group:
        groups.append(current_group)
    return groups
```

### `assemble_html` 改为按组拼 `<tr>`

```python
def assemble_html(slices, display_w=650):
    sorted_slices = sorted(slices, key=lambda s: s.sort_key)
    groups = _group_by_source(sorted_slices)
    rows = ""
    cid_counter = 0
    for group in groups:
        cells = ""
        for s in group:
            cid_counter += 1
            cid = f"slice_{cid_counter:03d}"
            cells += _build_cell(s.path, f"cid:{cid}", display_w, s.href, s.alt_text,
                                 s.original_width, is_base64=False)
        rows += f'<tr>\n{cells}</tr>\n'  # ✓ 同组 1 个 <tr> 多 <td>
    return html_template.format(rows=rows)
```

## 效果对比

| 场景 | 之前 | 现在 |
|------|------|------|
| 1 张原图 + 1 hotspot | 3 个 `<tr>` 纵向 | **1 个 `<tr>` 3 个 `<td>` 横向** |
| 2 张原图（Y 切） | 6 个 `<tr>` 纵向 | **2 个 `<tr>`（每原图 1 行）** |
| Outlook 视觉 | 3 张图垂直排列 = 1500px | 1 行图 = 650×500 = 完整原图 |
| 链接可点 | ✓ | ✓ |
| 显示宽度 | 错乱 | = display_w |

## 测试

`tests/test_v469_bug4.py` — 6 个测试：

- `test_one_image_one_hotspot_one_row_three_cells` — 主场景
- `test_no_hotspot_one_cell` — 无 hotspot 退化
- `test_two_hotspots_five_cells_in_one_row` — 多 hotspot
- `test_two_images_two_rows` — 多原图（Y 切）
- `test_total_width_equals_display_w` — 总宽 = display_w
- `test_link_in_correct_cell` — 链接在中间 `<td>`

## 复盘（gstack Iron Law 验证）

| 之前 V4.6.9 | 真正 V4.6.9 |
|-------------|------------|
| 修 Bug 3（多段宽度）就认为 OK | Step 4 直接打印 `<tr>` 数量 = 3 才命中根因 |
| 没主动调查"碎片化" | 按 5 步调查协议逐项排除嫌疑 |
| 直接改代码 | 先报告根因，等用户确认方案 A 才改 |

教训：**用户报告的"现象" ≠ 根因**。必须按 gstack 调查协议逐项验证，不能凭直觉猜。

## commit

- `978ab2c` — V4.6.9 Bug 4 修复（横向拼接）

---

_最后更新：2026-06-02_
