"""V4.8.9+ hotspot/button regression tests.

用户目标：添加可点击按钮后，发送到 Outlook 仍必须是一整张无缝长图；
多个按钮轻微贴边/压线时不应误报阻塞。
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clickable_map import Hotspot
from hotspot_slicer import slice_paths_by_hotspots, validate_hotspots_no_overlap
from html_assembler import SliceItem, materialize_display_slices


def test_hotspot_materialize_extends_right_edge_when_display_width_rounds_up(tmp_path):
    """650px 原图 + 按钮切条 + 652px Outlook 显示宽时，不得产生黑/白异常边。

    V4.8.8 把显示宽度归一到 4px 倍数：650 → 652。
    hotspot 纵向切条总宽仍是 650；旧 materialize 直接从 650px 源图裁 652px，
    Pillow 会用默认黑色填越界区域，Outlook 里表现为按钮路径后的竖向空隙/黑边。
    """
    src = tmp_path / "multi.png"
    Image.new("RGB", (650, 833), (0, 0, 255)).save(src)
    hotspots = {
        "multi.png": [
            Hotspot(100, 100, 180, 200, "https://a.example"),
            Hotspot(300, 100, 390, 200, "https://b.example"),
        ]
    }

    sliced, link_map = slice_paths_by_hotspots(
        [str(src)], hotspots, source_index_map={"multi.png": 1.0}
    )
    slices = [
        SliceItem(
            path=path,
            href=link_map.get(Path(path).name),
            sort_key=sort_key,
            original_width=650,
        )
        for path, sort_key in sliced
    ]

    prepared = materialize_display_slices(slices, 650)

    # 所有切条，包括最右侧补齐出来的 2px，都必须延展蓝色边缘，不允许默认黑/白边。
    for item in prepared:
        with Image.open(item.path) as out:
            for x in range(out.width):
                assert out.getpixel((x, 0)) == (0, 0, 255)
                assert out.getpixel((x, out.height - 1)) == (0, 0, 255)


def test_adjacent_button_tiny_overlap_is_snapped_instead_of_error():
    """一排多个按钮轻微压线（1~2px）应自动吸附边界，不应报横向重叠错误。

    用户拖选按钮不是像素级操作；相邻按钮轻微重叠属于 UI 容差，不应阻塞发送。
    """
    hotspots = [
        Hotspot(100, 100, 200, 180, "https://a.example"),
        Hotspot(198, 100, 300, 180, "https://b.example"),  # 2px 轻微重叠
        Hotspot(300, 100, 420, 180, "https://c.example"),
    ]

    ok, reason = validate_hotspots_no_overlap(hotspots, 650)
    assert ok, reason
    # B2 回归：校验函数必须是纯函数，吸附时不得写回入参。
    # 两个按钮原始坐标应保持不变（100-200 / 198-300），轻微压线被判定为无重叠、
    # 但不修改调用方持有的 hotspots 列表。
    assert hotspots[0].x2 == 200
    assert hotspots[1].x1 == 198
    assert hotspots[0].x2 != hotspots[1].x1
    # 第三个按钮也未受影响
    assert hotspots[2].x1 == 300 and hotspots[2].x2 == 420
