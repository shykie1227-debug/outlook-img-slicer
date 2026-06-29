from pathlib import Path

from PIL import Image

from image_slicer import detect_and_slice
from main import ProcessWorker
from clickable_map import Hotspot
from hotspot_slicer import slice_paths_by_hotspots


def test_same_named_images_use_isolated_temp_workspaces(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "campaign.png"
    second = second_dir / "campaign.png"
    Image.new("RGB", (650, 1800), "red").save(first)
    Image.new("RGB", (650, 1800), "blue").save(second)

    first_slices = detect_and_slice(str(first), max_height=1200)
    second_slices = detect_and_slice(str(second), max_height=1200)

    assert set(first_slices).isdisjoint(second_slices)
    with Image.open(first_slices[0]) as image:
        assert image.getpixel((20, 20)) == (255, 0, 0)
    with Image.open(second_slices[0]) as image:
        assert image.getpixel((20, 20)) == (0, 0, 255)


def test_scaled_outputs_do_not_reuse_source_basename(tmp_path):
    source = tmp_path / "wide.png"
    Image.new("RGB", (1200, 400), "green").save(source)

    first = detect_and_slice(str(source), target_width=650)
    second = detect_and_slice(str(source), target_width=650)

    assert first[0] != second[0]
    assert Path(first[0]).exists()
    assert Path(second[0]).exists()


def test_converted_small_page_survives_intermediate_workspace_cleanup():
    worker = ProcessWorker("document.pdf", width=650, smart=False)

    paths = worker._convert_and_slice(
        lambda _: [Image.new("RGB", (650, 500), "white")],
        "pdf_page",
        45,
        75,
    )

    assert len(paths) == 1
    assert Path(paths[0]).exists()
    assert Path(paths[0]).name.startswith("source_")


def test_hotspot_pieces_never_write_into_user_source_directory(tmp_path):
    source = tmp_path / "campaign.png"
    Image.new("RGB", (650, 400), "white").save(source)

    sliced, _ = slice_paths_by_hotspots(
        [str(source)],
        {
            source.name: [
                Hotspot(100, 100, 250, 180, "https://example.com")
            ]
        },
        source_index_map={source.name: 1.0},
    )

    generated = [Path(path) for path, _ in sliced]
    assert all(path.parent != tmp_path for path in generated)
    assert list(tmp_path.iterdir()) == [source]
