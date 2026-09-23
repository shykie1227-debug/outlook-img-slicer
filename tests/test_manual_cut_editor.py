from pathlib import Path

import pytest
from PIL import Image

import image_slicer

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _manual_api():
    validate = getattr(image_slicer, "validate_cut_positions", None)
    reslice = getattr(image_slicer, "reslice_existing_stack", None)
    assert callable(validate), "validate_cut_positions 尚未实现"
    assert callable(reslice), "reslice_existing_stack 尚未实现"
    return validate, reslice


def _complete_api():
    complete = getattr(image_slicer, "complete_cut_positions", None)
    assert callable(complete), "complete_cut_positions 尚未实现"
    return complete


def _make_vertical_gradient(path: Path, width: int, height: int) -> None:
    image = Image.new("RGB", (width, height))
    for y in range(height):
        color = (y % 251, (y * 3) % 251, (y * 7) % 251)
        for x in range(width):
            image.putpixel((x, y), color)
    image.save(path)


def _stack_pixels(paths: list[str]) -> list[tuple[int, int, int]]:
    pixels = []
    for path in paths:
        with Image.open(path) as image:
            pixels.extend(image.convert("RGB").getpixel((0, y)) for y in range(image.height))
    return pixels


def test_manual_cut_positions_reject_crossing_and_unsafe_heights():
    validate, _ = _manual_api()

    with pytest.raises(ValueError, match="递增"):
        validate(1800, [900, 800])
    with pytest.raises(ValueError, match="至少"):
        validate(1800, [40, 900])
    with pytest.raises(ValueError, match="1200"):
        validate(2500, [1300])


def test_manual_reslice_preserves_every_vertical_pixel(tmp_path):
    validate, reslice = _manual_api()
    source = tmp_path / "source.png"
    _make_vertical_gradient(source, 12, 1800)
    auto_dir = tmp_path / "auto"
    auto_dir.mkdir()
    first = auto_dir / "slice_1.png"
    second = auto_dir / "slice_2.png"
    with Image.open(source) as image:
        image.crop((0, 0, 12, 900)).save(first)
        image.crop((0, 900, 12, 1800)).save(second)

    cuts = validate(1800, [500, 1200])
    result = reslice([str(first), str(second)], cuts)

    assert [Image.open(path).height for path in result] == [500, 700, 600]
    assert _stack_pixels(result) == _stack_pixels([str(first), str(second)])
    assert all(Path(path).parent != auto_dir for path in result)


def test_manual_cut_positions_accept_outlook_safe_boundaries():
    validate, _ = _manual_api()

    assert validate(2400, [800, 1600]) == [800, 1600]


def test_free_manual_cut_is_preserved_and_long_sections_are_safely_completed():
    complete = _complete_api()

    positions = complete(2400, [300], min_height=80, max_height=1200)

    assert positions[0] == 300
    boundaries = [0, *positions, 2400]
    heights = [bottom - top for top, bottom in zip(boundaries, boundaries[1:])]
    assert all(80 <= height <= 1200 for height in heights)


def test_cut_editor_drag_is_not_locked_to_the_outlook_maximum(qapp, tmp_path):
    from cut_editor import CutEditorDialog

    paths = []
    for index in range(2):
        path = tmp_path / f"slice_{index}.png"
        Image.new("RGB", (600, 1200), "white").save(path)
        paths.append(str(path))

    dialog = CutEditorDialog(paths)
    try:
        line = dialog._line_items[0]
        assert round(dialog.clamp_scene_y(line, 300 * dialog._scale) / dialog._scale) == 300
    finally:
        dialog.close()


def _editor(qapp, tmp_path, heights=(1200, 1200), width=600):
    from cut_editor import CutEditorDialog

    paths = []
    for index, height in enumerate(heights):
        path = tmp_path / f"edit_{index}.png"
        Image.new("RGB", (width, height), "white").save(path)
        paths.append(str(path))
    return CutEditorDialog(paths)


def test_cut_editor_can_add_and_remove_a_single_cut_line(qapp, tmp_path):
    """顶部「＋新增切线」可以插到最宽区间中间，「－删除切线」删掉选中的那条。"""
    dialog = _editor(qapp, tmp_path)
    try:
        assert dialog.cut_positions() == [1200]
        assert dialog.btn_remove.isEnabled() is False, "未选中任何切线时删除按钮应置灰"

        dialog.add_cut_line()
        assert dialog.cut_positions() == [600, 1200]
        # 新增后新线自动选中，此时删除按钮应可用
        assert dialog.btn_remove.isEnabled() is True

        dialog.add_cut_line()
        assert dialog.cut_positions() == [600, 900, 1200]

        dialog.remove_cut_line()
        assert dialog.cut_positions() == [600, 1200]
    finally:
        dialog.close()


def test_cut_editor_added_line_keeps_line_order_sorted(qapp, tmp_path):
    """新增切线必须插进 _line_items 的正确位置，否则 clamp_scene_y 的前后判定会错乱。"""
    dialog = _editor(qapp, tmp_path)
    try:
        dialog.add_cut_line()
        dialog.scene.clearSelection()
        dialog.add_cut_line()
        ys = [round(line.pos().y() / dialog._scale) for line in dialog._line_items]
        assert ys == sorted(ys)
        assert dialog._line_items == sorted(dialog._line_items, key=lambda item: item.pos().y())
    finally:
        dialog.close()


def test_cut_editor_add_is_blocked_when_no_gap_can_be_split(qapp, tmp_path, monkeypatch):
    """总高只有 200px（每片 100px）时再切一刀必然违反 80px 下限，新增按钮应禁用。"""
    import cut_editor

    warned = []

    class _FakeMessageBox:
        @staticmethod
        def information(*args, **kwargs):
            warned.append(args)

    monkeypatch.setattr(cut_editor, "QMessageBox", _FakeMessageBox)

    dialog = _editor(qapp, tmp_path, heights=(100, 100))
    try:
        assert dialog.cut_positions() == [100]
        assert dialog.btn_add.isEnabled() is False
        before = dialog.cut_positions()
        dialog.add_cut_line()
        assert dialog.cut_positions() == before, "空间不足时不得插入切线"
        assert warned, "空间不足时应明确提示，而不是静默失败"
    finally:
        dialog.close()


def test_cut_editor_added_line_respects_minimum_slice_height(qapp, tmp_path):
    dialog = _editor(qapp, tmp_path)
    try:
        for _ in range(6):
            dialog.add_cut_line()
        boundaries = [0, *dialog.cut_positions(), dialog.total_height]
        heights = [b - a for a, b in zip(boundaries, boundaries[1:])]
        assert all(height >= dialog.MIN_SLICE_HEIGHT for height in heights)
    finally:
        dialog.close()


def test_cut_editor_reset_discards_manual_lines(qapp, tmp_path):
    """恢复自动切线必须把用户新增/删除过的切线一并还原，而不是只挪位置。"""
    dialog = _editor(qapp, tmp_path)
    try:
        dialog.add_cut_line()
        dialog.add_cut_line()
        assert len(dialog._line_items) == 3

        dialog.reset_positions()
        assert dialog.cut_positions() == [1200]
        assert len(dialog._line_items) == 1
        assert [round(line.pos().y() / dialog._scale) for line in dialog._line_items] == [1200]
        assert dialog.btn_remove.isEnabled() is False
        assert dialog.btn_add.isEnabled() is True
    finally:
        dialog.close()


def test_cut_editor_toolbar_fits_the_minimum_window_width(qapp, tmp_path):
    """顶部三个按钮在最小窗口宽度（520px）下不得被截断/溢出。"""
    dialog = _editor(qapp, tmp_path)
    try:
        assert dialog.minimumSizeHint().width() <= 520
        needed = sum(
            button.sizeHint().width()
            for button in (dialog.btn_add, dialog.btn_remove, dialog.btn_reset)
        )
        needed += 2 * 8 + 36  # 按钮间距 + 左右内容边距
        assert needed <= 520, f"顶部工具栏最小需要 {needed}px，超过最小窗口宽 520px"
    finally:
        dialog.close()


def test_cut_editor_removed_line_positions_are_used_by_apply(qapp, tmp_path):
    """删除切线后点「应用切线」，提交的切线集合必须不含被删掉的那条。"""
    dialog = _editor(qapp, tmp_path)
    try:
        dialog.add_cut_line()
        dialog.add_cut_line()
        dialog.scene.clearSelection()
        middle = dialog._line_items[1]
        middle.setSelected(True)
        dialog.remove_cut_line()

        dialog._accept_if_valid()
        applied = dialog.get_cut_positions()
        assert 900 not in applied, f"被删除的切线仍在提交结果中：{applied}"
        assert 600 in applied and 1200 in applied
    finally:
        dialog.close()
