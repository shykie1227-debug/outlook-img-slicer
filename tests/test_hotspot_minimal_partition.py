from PIL import Image

from clickable_map import Hotspot
from hotspot_slicer import slice_image_with_hotspots


def test_two_staggered_buttons_create_minimal_nine_pieces():
    image = Image.new("RGB", (960, 1200), "white")
    hotspots = [
        Hotspot(80, 100, 260, 180, "https://top.example"),
        Hotspot(650, 900, 880, 980, "https://bottom.example"),
    ]

    stripes = slice_image_with_hotspots(image, hotspots, source_index=1.0)

    assert len(stripes) == 9
    assert sum(stripe.href is not None for stripe in stripes) == 2
    assert sum(stripe.image.width * stripe.image.height for stripe in stripes) == 960 * 1200


def test_each_visual_row_uses_only_its_active_button_boundaries():
    image = Image.new("RGB", (960, 1200), "white")
    hotspots = [
        Hotspot(80, 100, 260, 180, "https://top.example"),
        Hotspot(650, 900, 880, 980, "https://bottom.example"),
    ]

    stripes = slice_image_with_hotspots(image, hotspots, source_index=1.0)
    widths_by_row: dict[tuple[int, int], list[int]] = {}
    for stripe in stripes:
        widths_by_row.setdefault((stripe.y1, stripe.y2), []).append(stripe.image.width)

    assert widths_by_row[(100, 180)] == [80, 180, 700]
    assert widths_by_row[(900, 980)] == [650, 230, 80]
    assert widths_by_row[(180, 900)] == [960]
