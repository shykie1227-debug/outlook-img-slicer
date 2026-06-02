# Bug 3：多段拼接宽度按原图比例缩放

> V4.6.9 修复  ·  严重程度：中  ·  涉及文件：`html_assembler.py` + `main.py`

---

## 现象

V1 物理切割后，1 张原图被切成 N 段（如标 1 个 hotspot → 3 段），邮件里视觉上总宽 = N × display_w，**远超原图按 display_w 缩放后的实际宽度**。

### 例子
- 原图：1000 × 500
- 1 个 hotspot：(400, 100) → (600, 400)
- 切割：3 段 (400×500 + 200×500 + 400×500)
- 邮件 display_w = 650
- **Bug 行为**：每段都按 650 渲染 → 总宽 = 1950px（错的，原图按 650 缩放应该是 650px）
- **正确行为**：每段按 650 × (400/1000) = 260、650 × 0.2 = 130、260 渲染 → 总宽 = 650 ✓

## 根因

`_build_image_row` 不看原图宽，每段都按 `display_w` 渲染：

```python
# 修复前 html_assembler.py
def _build_image_row(slice_path, cid, display_w, href=None, alt=""):
    actual_w, actual_h = _get_img_dimensions(slice_path)
    display_h = round(actual_h * display_w / actual_w)  # ❌ 直接用 display_w
    ...
    img_tag = f'<img src="cid:{cid}" width="{display_w}" height="{display_h}" ... />'
```

## 修复

### 1. SliceItem 加 `original_width` 字段

```python
# html_assembler.py
@dataclass
class SliceItem:
    path: str
    href: Optional[str] = None
    alt_text: str = ""
    sort_key: float = 0.0
    # V4.6.9 修复：原图宽度，用于多段拼接时按比例缩放
    original_width: int = 0
```

### 2. `_build_image_row` 按比例分配

```python
def _build_image_row(slice_path, cid, display_w, href=None, alt="", original_width=0):
    actual_w, actual_h = _get_img_dimensions(slice_path)

    # V4.6.9 修复：按原图宽比例分配
    if original_width > 0 and actual_w > 0:
        ratio = actual_w / original_width
        seg_display_w = round(display_w * ratio)
    else:
        seg_display_w = display_w  # 兜底
    seg_display_h = round(actual_h * seg_display_w / actual_w) if actual_w else 650
    ...
```

### 3. main.py 集成：从 sort_key 整数部分反推原图宽

```python
# main.py _build_slices_with_hotspots
source_idx = int(sk)  # 1.001 → 1
orig_path = si_to_orig.get(float(source_idx), '')
if orig_path and orig_path not in orig_w_cache:
    try:
        with _PIL_Image.open(orig_path) as im:
            orig_w_cache[orig_path] = im.size[0]
    except Exception:
        orig_w_cache[orig_path] = 0
orig_w = orig_w_cache.get(orig_path, 0)
items.append(SliceItem(..., original_width=orig_w))
```

## 效果

| 场景 | 之前 | 现在 |
|------|------|------|
| 1000×500 + 1 hotspot 切 3 段 | 总宽 1950 | **总宽 650** ✓ |
| 1000×500 + 2 hotspot 切 5 段 (200/100/400/100/200) | 总宽 3250 | **总宽 650** ✓ |

## 测试

`tests/test_v469_bug3.py` — 4 个测试覆盖：

- `test_single_hotspot_3_stripes_total_650` — 主场景
- `test_no_hotspot_single_slice_total_650` — 无 hotspot 退化为 1 段
- `test_no_original_width_falls_back_to_display_w` — 向后兼容
- `test_multiple_hotspots_proportional` — 多 hotspot 比例分配

## commit

- `a351cd7` — V4.6.9 Bug 3 修复

---

_最后更新：2026-06-02_
