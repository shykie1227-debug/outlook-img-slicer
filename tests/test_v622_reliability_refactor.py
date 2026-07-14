import json
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

import main
from clickable_map import Hotspot, HotspotMap
from desktop.hotspot_editor import HotspotEditorDialog
from html_assembler import SliceItem, materialize_display_slices


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_stale_worker_result_cannot_replace_current_document(qapp, tmp_path):
    current = tmp_path / "current.png"
    stale = tmp_path / "stale.png"
    Image.new("RGB", (200, 100), "green").save(current)
    Image.new("RGB", (200, 100), "red").save(stale)

    win = main.MainWindow()
    try:
        win.slice_paths = [str(current)]
        win._active_job_id = 7
        win._on_processed([str(stale)], job_id=6)

        assert win.slice_paths == [str(current)]
    finally:
        win.close()


def test_hotspot_editor_cancel_is_transactional(qapp, tmp_path):
    image_path = tmp_path / "slice.png"
    Image.new("RGB", (400, 240), "white").save(image_path)
    hotspot_map = HotspotMap()
    hotspot_map.add(
        image_path.name,
        Hotspot(20, 20, 120, 80, "https://original.example"),
    )

    dialog = HotspotEditorDialog(str(image_path), hotspot_map)
    try:
        ok, reason = dialog._working_map.add(
            image_path.name,
            Hotspot(180, 100, 320, 180, "https://draft.example"),
        )
        assert ok, reason
        dialog.reject()

        saved = hotspot_map.get(image_path.name)
        assert len(saved) == 1
        assert saved[0].url == "https://original.example"
    finally:
        dialog.close()


def test_hotspot_materialize_uses_one_global_resize(tmp_path):
    source = Image.new("RGB", (1000, 602))
    for y in range(source.height):
        for x in range(source.width):
            source.putpixel((x, y), ((x + y) % 251, (2 * x + y) % 253, (x + 3 * y) % 255))

    # Two rows, each split into two columns, matching hotspot_slicer sort keys.
    items = []
    for row, (top, bottom) in enumerate(((0, 301), (301, 602)), start=1):
        for col, (left, right) in enumerate(((0, 437), (437, 1000)), start=1):
            path = tmp_path / f"r{row}c{col}.png"
            source.crop((left, top, right, bottom)).save(path)
            items.append(SliceItem(
                path=str(path),
                href=f"https://r{row}c{col}.example" if col == 2 else None,
                sort_key=1 + row / 1000 + col / 1_000_000,
                original_width=1000,
            ))

    prepared = materialize_display_slices(items, 648)
    rows = {}
    for item in prepared:
        row = int((item.sort_key - int(item.sort_key)) * 1000 + 1e-6)
        rows.setdefault(row, []).append(item)

    reconstructed_rows = []
    for row in sorted(rows):
        parts = [Image.open(item.path).convert("RGB") for item in sorted(rows[row], key=lambda i: i.sort_key)]
        canvas = Image.new("RGB", (sum(p.width for p in parts), parts[0].height))
        x = 0
        for part in parts:
            canvas.paste(part, (x, 0))
            x += part.width
        reconstructed_rows.append(canvas)

    reconstructed = Image.new("RGB", (648, sum(row.height for row in reconstructed_rows)))
    y = 0
    for row in reconstructed_rows:
        reconstructed.paste(row, (0, y))
        y += row.height

    expected = source.resize(reconstructed.size, Image.Resampling.LANCZOS)
    assert reconstructed.tobytes() == expected.tobytes()


def test_build_manifest_contract_is_machine_readable():
    build_source = (Path(__file__).parents[1] / "desktop" / "build.py").read_text(encoding="utf-8")
    build_ps1 = (Path(__file__).parents[1] / "build.ps1").read_text(encoding="utf-8")
    vm_ps1 = (Path(__file__).parents[1] / "vm_build.ps1").read_text(encoding="utf-8")

    assert "build-manifest.json" in build_source
    assert "sha256" in build_source
    assert "build-manifest.json" in build_ps1
    assert "build-manifest.json" in vm_ps1
    assert "Get-Content" in build_ps1 and "ConvertFrom-Json" in build_ps1
