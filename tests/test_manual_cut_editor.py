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
