"""
B2 回归测试：validate_hotspots_no_overlap 不得原地修改入参 hotspots

根因（hotspot_slicer.py）：边缘吸附分支在 x_overlap<=容差时直接
`a.x2 = b.x1` / `b.x2 = a.x1`，对调用方持有的 hotspots 列表产生隐式副作用。
修复：吸附在「副本」上计算，绝不写回入参；校验函数保持纯函数。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clickable_map import Hotspot
from hotspot_slicer import validate_hotspots_no_overlap


def test_validate_does_not_mutate_input_on_edge_snap():
    """一排按钮轻微压线（1~2px）自动吸附判定为无重叠，但入参坐标完全不变。"""
    hotspots = [
        Hotspot(100, 100, 200, 180, "https://a.example"),
        Hotspot(198, 100, 300, 180, "https://b.example"),  # 2px 轻微重叠
        Hotspot(300, 100, 420, 180, "https://c.example"),
    ]
    originals = [(h.x1, h.x2, h.y1, h.y2) for h in hotspots]

    ok, reason = validate_hotspots_no_overlap(hotspots, 650)
    assert ok, reason

    for h, orig in zip(hotspots, originals):
        assert (h.x1, h.x2, h.y1, h.y2) == orig, "校验函数修改了入参 hotspots（B2 回归）"


def test_validate_returns_error_for_real_overlap():
    """真实矩形重叠仍应被拒绝（吸附只处理压线容差，不动真实重叠判定）。"""
    hotspots = [
        Hotspot(100, 100, 300, 200, "https://a.example"),
        Hotspot(200, 100, 400, 200, "https://b.example"),  # 真实重叠
    ]
    ok, reason = validate_hotspots_no_overlap(hotspots, 650)
    assert not ok
    assert "重叠" in reason


def test_validate_does_not_mutate_on_real_overlap_error():
    """即使判定为重叠报错，也不应修改入参（纯函数语义）。"""
    hotspots = [
        Hotspot(100, 100, 300, 200, "https://a.example"),
        Hotspot(200, 100, 400, 200, "https://b.example"),
    ]
    originals = [(h.x1, h.x2, h.y1, h.y2) for h in hotspots]
    validate_hotspots_no_overlap(hotspots, 650)
    for h, orig in zip(hotspots, originals):
        assert (h.x1, h.x2, h.y1, h.y2) == orig
