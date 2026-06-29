from pathlib import Path

import pytest
from PIL import Image

import image_slicer


def _manual_api():
    validate = getattr(image_slicer, "validate_cut_positions", None)
    reslice = getattr(image_slicer, "reslice_existing_stack", None)
    assert callable(validate), "validate_cut_positions 尚未实现"
    assert callable(reslice), "reslice_existing_stack 尚未实现"
    return validate, reslice


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
