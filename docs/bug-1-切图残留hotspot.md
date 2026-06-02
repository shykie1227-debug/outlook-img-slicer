# Bug 1：切图残留 hotspot_map

> V4.6.9 修复  ·  严重程度：中  ·  涉及文件：`main.py`

---

## 现象

用户在 A 图上标注 hotspot 后，拖入新图 B → 旧图 A 的 hotspot 仍残留在 `hotspot_map` 中。

## 根因

`_on_processed` 是 `ProcessWorker` 处理完切图后的回调，负责更新 `slice_paths` 和 `slice_source_index`。但它**没有清空 `hotspot_map`**，导致旧图的 hotspot 跨切图残留。

```python
# main.py:793 _on_processed
def _on_processed(self, paths: List[str]):
    self.slice_paths = paths
    self.slice_source_index = {
        os.path.basename(p): float(i + 1) for i, p in enumerate(paths)
    }
    # ❌ 缺：self.hotspot_map.clear()
    self.progress_bar.hide()
    ...
```

## 实际影响

表面上不会"破坏"新图——`slice_paths_by_hotspots` 用 `hotspots_by_slice.get(fname, [])` 查 B 的 `b1.png`，查不到 → 默认 `[]` → B 的切片不会被错误切割。

但引发**用户认知错乱**："为什么我切了新图，旧图的 hotspot 还在？"

## 修复

```python
# V4.6.9 main.py:800
def _on_processed(self, paths: List[str]):
    self.slice_paths = paths
    self.slice_source_index = {
        os.path.basename(p): float(i + 1) for i, p in enumerate(paths)
    }
    # V4.6.9 修复：重新切图时必须清空 hotspot_map
    self.hotspot_map.clear()  # ✓
    self.progress_bar.hide()
    ...
```

## 验证测试

`tests/test_v469_bug1.py`：

```python
def test_no_residual_hotspot_after_clear(self):
    """清空后 _build_slices_with_hotspots 不会用旧 hotspot"""
    from clickable_map import Hotspot, HotspotMap
    from hotspot_slicer import slice_paths_by_hotspots

    hm = HotspotMap()
    hm.add('a1.png', Hotspot(0, 0, 100, 100, 'https://a.com'), source_index=1.0)
    assert hm.all_slices() == ['a1.png']

    hm.clear()
    assert hm.is_empty()

    hm.add('b1.png', Hotspot(0, 0, 200, 200, 'https://b.com'), source_index=1.0)
    assert hm.all_slices() == ['b1.png']  # 只剩 B 的
    assert hm.total_count() == 1
```

## 关联

- 与 `reset_app` 一致：用户点"重置"按钮时也清 `hotspot_map`
- V4.6.7 排序架构：清空不影响 `slice_source_index`（独立字段）

## commit

- `22e7566` — V4.6.9 首次提交（仅 Bug 1 修复）
- `a351cd7` — V4.6.9 amend 重新提交（合并多 commit + tests）
- `978ab2c` — V4.6.9 最终版（Bug 4 修复）

---

_最后更新：2026-06-02_
