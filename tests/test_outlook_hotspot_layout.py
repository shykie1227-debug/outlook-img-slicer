from pathlib import Path

from PIL import Image

from clickable_map import Hotspot
from hotspot_slicer import slice_paths_by_hotspots
from html_assembler import (
    SliceItem,
    _group_by_source,
    assemble_html,
    materialize_display_slices_strict,
)


def _prepared_hotspot_items(tmp_path: Path) -> list[SliceItem]:
    source = tmp_path / "long.png"
    Image.new("RGB", (650, 600), "white").save(source)
    hotspots = {
        source.name: [
            Hotspot(60, 80, 210, 150, "https://top.example"),
            Hotspot(410, 420, 590, 500, "https://bottom.example"),
        ]
    }
    sliced, links = slice_paths_by_hotspots(
        [str(source)],
        hotspots,
        source_index_map={source.name: 1.0},
    )
    raw = [
        SliceItem(
            path=path,
            href=links.get(Path(path).name),
            sort_key=sort_key,
            original_width=650,
        )
        for path, sort_key in sliced
    ]
    return materialize_display_slices_strict(raw, 648)


def test_hotspot_rows_do_not_share_or_nest_table_columns(tmp_path):
    prepared = _prepared_hotspot_items(tmp_path)
    html = assemble_html(prepared, 648)

    assert html.count("<table") == 1
    assert html.count("<div") == len(_group_by_source(prepared))
    assert "<tr height=" not in html


def test_hotspot_links_are_inline_while_images_remain_block(tmp_path):
    prepared = _prepared_hotspot_items(tmp_path)
    html = assemble_html(prepared, 648)

    assert "https://top.example" in html
    assert "https://bottom.example" in html
    assert 'style="display: inline-block;' in html
    assert "<img" in html and "display: block;" in html
