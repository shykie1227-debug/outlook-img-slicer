"""
画布原点对齐回归测试（V6.4.0）。

缺陷现场（修复前实测）：
  ImageCanvas 用「请求宽度」算 scale（800 / actual_w），但 Qt.KeepAspectRatio
  实际返回的位图只有 797/799px；同时 setMinimumSize 用的是请求尺寸、
  QLabel 默认 AlignLeft | AlignVCenter 又把位图垂直居中 ——
  三个误差叠加后，短切片（900x140）的位图原点比画布原点低 16px、
  右侧留 49px 白边。paintEvent 按 (0,0) 画热区、鼠标按 (0,0) 换算坐标，
  结果就是"用户看到的按钮框"和"实际存下来的坐标"对不上。

为什么这里只测 ImageCanvas、不实例化 HotspotEditorDialog：
  实测（干净字节码缓存下 3/3 稳定复现）—— 让「文件名排序最靠前的 Qt 模块」
  构造 HotspotEditorDialog，整套用例必在 tests/test_v491_hotspot_disabled.py
  段错误，崩点 desktop/main.py:502 的 super().__init__()。
  该现象**与本次改动无关**：把 desktop/hotspot_editor.py 整体回退到 HEAD
  后同样复现。本文件按文件名排序最先运行，故刻意避开对话框构造；
  对话框侧的几何入口由 test_refit_delegates_to_apply_scaled_pixmap
  用「未绑定方法 + 轻量 stub」覆盖，同样不构造对话框。
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QScrollArea

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clickable_map import Hotspot

# 注意：不要在本文件里定义 `qapp`。
# QApplication 必须是会话级单例并全程存活 —— 一旦被 GC 回收，
# 后续模块构造 QWidget 会段错误。会话级 fixture 见 tests/conftest.py。


def _make_slice(tmp_path: Path, name: str, size) -> Path:
    path = tmp_path / name
    Image.new("RGB", size, (120, 160, 200)).save(path)
    return path


def _new_canvas(path: Path, size, target_width: int = 800):
    from hotspot_editor import ImageCanvas

    return ImageCanvas(str(path), size, [], target_width=target_width)


def _canvas_invariants(canvas):
    """修复后的硬性不变量（决定"看到的框"和"存下的坐标"是否一致）。"""
    assert canvas.display_w == canvas.pixmap.width(), (
        f"display_w={canvas.display_w} 与实际位图宽 {canvas.pixmap.width()} 不一致"
    )
    assert canvas.display_h == canvas.pixmap.height(), (
        f"display_h={canvas.display_h} 与实际位图高 {canvas.pixmap.height()} 不一致"
    )
    assert abs(canvas.scale - canvas.pixmap.width() / canvas.actual_w) < 1e-9, (
        "scale 必须按实际位图宽计算，否则坐标换算整体偏移"
    )
    assert canvas.alignment() == (Qt.AlignLeft | Qt.AlignTop), (
        "位图必须钉在画布左上角，原点错开会导致绘制与取值都偏移"
    )


def test_short_slice_canvas_origin_matches_pixmap_origin(qapp, tmp_path):
    """短宽切片（KeepAspectRatio 会横向缩水）——修复前偏移 16px 的现场。"""
    path = _make_slice(tmp_path, "short.png", (900, 140))
    canvas = _new_canvas(path, (900, 140))
    try:
        _canvas_invariants(canvas)
        # 位图原点与画布原点重合 → 任何热区的绘制矩形都必须落在位图内部
        canvas.set_hotspots([Hotspot(20, 10, 500, 120, "https://example.com")])
        scale = canvas.scale
        painted_bottom = int(120 * scale)
        painted_right = int(500 * scale)
        assert painted_bottom <= canvas.pixmap.height(), (
            f"绘制矩形底边 {painted_bottom} 超出位图高度 {canvas.pixmap.height()} → 有偏移"
        )
        assert painted_right <= canvas.pixmap.width()
    finally:
        canvas.deleteLater()


def test_tall_slice_canvas_origin_matches_pixmap_origin(qapp, tmp_path):
    """长切片（KeepAspectRatio 会纵向缩水）——修复前右侧留 29px 白边。"""
    path = _make_slice(tmp_path, "tall.png", (900, 3000))
    canvas = _new_canvas(path, (900, 3000))
    try:
        _canvas_invariants(canvas)
    finally:
        canvas.deleteLater()


def test_canvas_invariants_hold_across_width_changes(qapp, tmp_path):
    """宽度变化（窗口 resize 的等价路径）后，四条不变量仍必须成立。"""
    path = _make_slice(tmp_path, "resize.png", (900, 140))
    canvas = _new_canvas(path, (900, 140))
    try:
        _canvas_invariants(canvas)
        for width in (700, 560, 400, 800):
            canvas.apply_scaled_pixmap(width)
            QApplication.processEvents()
            _canvas_invariants(canvas)
    finally:
        canvas.deleteLater()


def test_refit_delegates_to_apply_scaled_pixmap(qapp, tmp_path, monkeypatch):
    """
    对话框侧 resize 路径（_refit_canvas_to_size）必须把几何交给
    apply_scaled_pixmap，不能再自己手算 display_w/scale —— 那正是偏移根源。

    这里用「未绑定方法 + 轻量 stub」调用，不构造 HotspotEditorDialog
    （原因见模块 docstring）。
    """
    from hotspot_editor import HotspotEditorDialog, ImageCanvas

    path = _make_slice(tmp_path, "stub.png", (900, 140))
    canvas = _new_canvas(path, (900, 140))
    scroll = QScrollArea()
    scroll.setWidget(canvas)  # _refit 要沿 parent 链找 QScrollArea
    try:
        calls = []
        original = ImageCanvas.apply_scaled_pixmap

        def spy(self, target_w, target_h=None):
            calls.append(target_w)
            return original(self, target_w, target_h)

        monkeypatch.setattr(ImageCanvas, "apply_scaled_pixmap", spy)
        canvas._requested_w = None  # 避免命中「宽度未变」的提前返回
        HotspotEditorDialog._refit_canvas_to_size(SimpleNamespace(canvas=canvas))

        assert calls, "_refit_canvas_to_size 必须走 apply_scaled_pixmap"
        _canvas_invariants(canvas)
    finally:
        scroll.deleteLater()


def test_coordinate_roundtrip_through_scale(qapp, tmp_path):
    """拖框选的换算链路：actual → widget → actual 必须还原（误差 <= 1px）。"""
    path = _make_slice(tmp_path, "rt.png", (900, 140))
    canvas = _new_canvas(path, (900, 140))
    try:
        scale = canvas.scale
        for actual in ((20, 10), (500, 120), (899, 139)):
            widget_x = int(actual[0] * scale)
            widget_y = int(actual[1] * scale)
            assert abs(widget_x / scale - actual[0]) <= 1.0
            assert abs(widget_y / scale - actual[1]) <= 1.0
            assert widget_x <= canvas.pixmap.width()
            assert widget_y <= canvas.pixmap.height()
    finally:
        canvas.deleteLater()
