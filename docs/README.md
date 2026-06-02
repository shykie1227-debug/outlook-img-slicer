# docs/ 目录索引

> 维护：王萧铭  ·  最后更新：2026-06-02  ·  工具版本：V4.6.9

---

## 📚 文档结构

```
docs/
├── README.md                       # 本文件（索引）
├── V4.6.9-修复总结.md              # ⭐ V4.6.9 修复总结（必读）
├── 功能说明书.md                    # 产品功能说明（用户视角）
│
├── bug-1-切图残留hotspot.md         # Bug 1：_on_processed 残留
├── bug-3-多段拼接按比例缩放.md      # Bug 3：多段宽度比例
├── bug-4-HTML横向拼接.md            # Bug 4：HTML 横向拼接（真正根因）
│
├── 架构-V1物理切割.md               # V1 物理切割架构
├── 架构-V4.6.7排序架构.md           # V4.6.7 显式 sort_key 架构
│
└── 技能-gstack-openclaw-investigate.md  # 系统性调试方法论
```

---

## 🎯 快速导航

### 我是用户 / 客户
- [功能说明书.md](./功能说明书.md) — 产品功能 + 兼容性 + 限制

### 我要修 bug
- [V4.6.9-修复总结.md](./V4.6.9-修复总结.md) — 最近 3 个 bug 的根因 + 修复
- [技能-gstack-openclaw-investigate.md](./技能-gstack-openclaw-investigate.md) — 调查方法论

### 我要理解架构
- [架构-V1物理切割.md](./架构-V1物理切割.md) — 为什么物理切割
- [架构-V4.6.7排序架构.md](./架构-V4.6.7排序架构.md) — sort_key 数值层级

### 我要 review 代码
- [V4.6.9-修复总结.md#测试覆盖](./V4.6.9-修复总结.md) — 14/14 pytest 通过
- `tests/test_v469_*.py` — 测试源码

---

## 📋 V4.6.9 核心改进一览

| Bug | 严重 | 修复 | 文档 |
|-----|------|------|------|
| Bug 1：切图残留 hotspot_map | 中 | `_on_processed` 加 `clear()` | [link](./bug-1-切图残留hotspot.md) |
| Bug 3：多段拼接宽度按比例 | 中 | `SliceItem` 加 `original_width` | [link](./bug-3-多段拼接按比例缩放.md) |
| Bug 4：HTML 横向拼接 | **高** | 拆 `_build_image_row` 为 `_build_cell` + `_group_by_source` | [link](./bug-4-HTML横向拼接.md) |

---

## 🧪 测试覆盖

| 文件 | 测试数 | 覆盖 |
|------|--------|------|
| `tests/test_v469_bug1.py` | 4 | Bug 1 修复 |
| `tests/test_v469_bug3.py` | 4 | Bug 3 修复 |
| `tests/test_v469_bug4.py` | 6 | Bug 4 修复 |
| **总计** | **14** | **V4.6.9 全部修复** |

运行：`python3 -m pytest tests/ -v`

---

## 🔧 工具链

- Python 3.11
- PySide6（GUI）
- Pillow（图像）
- PyMuPDF（PDF）
- python-pptx（PPT）
- psd-tools + numpy（PSD）
- pywin32（Outlook COM，Windows only）
- PyInstaller（打包）

打包：`python build.py`（Windows）
产物：`dist/Outlook长图插入工具.exe`（约 92MB）

---

_最后更新：2026-06-02_
