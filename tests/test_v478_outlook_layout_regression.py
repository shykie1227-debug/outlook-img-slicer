"""
V4.7.8 Outlook 布局回归测试

覆盖：
- 邮件显示宽度统一偶数化，外层 table 与内层切片总宽一致
- 多个可点击按钮切成多段后，预渲染图片尺寸与 HTML 声明一致
- CID 顺序与 sort_key 排序后的附件顺序一致
- 运行时不引入 PyQt5 依赖
"""
import os
import re
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clickable_map import Hotspot
from hotspot_slicer import slice_paths_by_hotspots
from html_assembler import (
    SliceItem,
    _allocate_group_widths,
    _normalize_display_width,
    assemble_html,
    generate_plain_html,
    materialize_display_slices,
    materialize_display_slices_strict,
)


def make_image(path: Path, w: int, h: int):
    Image.new("RGB", (w, h), "white").save(path)


def build_hotspot_slices(tmp_path: Path, display_w: int = 651):
    p = tmp_path / "multi.png"
    make_image(p, 1000, 501)
    hotspots = {
        "multi.png": [
            Hotspot(180, 0, 260, 501, "https://a.example", "A", source_index=1.0),
            Hotspot(520, 0, 650, 501, "https://b.example", "B", source_index=1.0),
            Hotspot(810, 0, 920, 501, "https://c.example", "C", source_index=1.0),
        ]
    }
    sliced, link_map = slice_paths_by_hotspots(
        [str(p)], hotspots, source_index_map={"multi.png": 1.0}
    )
    return [
        SliceItem(
            path=path,
            href=link_map.get(os.path.basename(path)),
            alt_text="",
            sort_key=sort_key,
            original_width=1000,
        )
        for path, sort_key in sliced
    ], display_w


def test_odd_display_width_is_normalized_everywhere(tmp_path):
    slices, display_w = build_hotspot_slices(tmp_path, display_w=651)
    expected_w = _normalize_display_width(display_w)
    prepared = materialize_display_slices(slices, display_w)
    html = generate_plain_html(prepared, display_w)

    assert expected_w == 650
    assert f'width="{expected_w}"' in html

    sizes = [Image.open(s.path).size for s in prepared]
    assert sum(w for w, _ in sizes) == expected_w
    assert all(w % 2 == 0 for w, _ in sizes)
    assert len({h for _, h in sizes}) == 1
    assert next(iter({h for _, h in sizes})) % 2 == 0

    img_widths = [int(w) for w in re.findall(r'<img[^>]*width="(\d+)"', html)]
    assert img_widths == [w for w, _ in sizes]
    assert sum(img_widths) == expected_w


def test_multiple_hotspots_keep_precise_even_widths(tmp_path):
    slices, _ = build_hotspot_slices(tmp_path, display_w=960)
    widths = _allocate_group_widths(slices, 960)

    assert sum(widths[s.path] for s in slices) == 960
    assert all(widths[s.path] % 2 == 0 for s in slices)
    assert len(widths) == 7  # 3 buttons produce 7 vertical stripes

    prepared = materialize_display_slices(slices, 960)
    html = assemble_html(prepared, 960)
    assert html.count("<a href=") == 3
    assert "mso-line-height-rule: exactly" in html
    assert "mso-table-lspace: 0pt" in html
    assert "mso-table-rspace: 0pt" in html
    assert "mso-table-bspace: 0pt" in html
    assert "mso-table-tspace: 0pt" in html


def test_plain_vertical_slices_use_flat_rows_without_nested_tables(tmp_path):
    p1 = tmp_path / "slice_001.png"
    p2 = tmp_path / "slice_002.png"
    p3 = tmp_path / "slice_003.png"
    make_image(p1, 650, 547)
    make_image(p2, 650, 552)
    make_image(p3, 650, 549)
    slices = [
        SliceItem(path=str(p1), sort_key=1.0, original_width=650),
        SliceItem(path=str(p2), sort_key=2.0, original_width=650),
        SliceItem(path=str(p3), sort_key=3.0, original_width=650),
    ]

    prepared = materialize_display_slices_strict(slices, 650)
    html = assemble_html(prepared, 650)

    assert html.count("<table") == 1
    assert html.count("<tr height=") == 3
    assert "mso-margin-top-alt: 0" in html
    assert "mso-margin-bottom-alt: 0" in html
    assert "table-layout: fixed" in html


def test_cid_order_matches_sorted_slice_order(tmp_path):
    p1 = tmp_path / "top.png"
    p2 = tmp_path / "bottom.png"
    make_image(p1, 800, 300)
    make_image(p2, 800, 300)

    hotspots = {
        "top.png": [Hotspot(200, 0, 400, 300, "https://top.example", "T", source_index=1.0)],
        "bottom.png": [Hotspot(500, 0, 650, 300, "https://bottom.example", "B", source_index=2.0)],
    }
    sliced, link_map = slice_paths_by_hotspots(
        [str(p1), str(p2)],
        hotspots,
        source_index_map={"top.png": 1.0, "bottom.png": 2.0},
    )
    slices = [
        SliceItem(
            path=path,
            href=link_map.get(os.path.basename(path)),
            sort_key=sort_key,
            original_width=800,
        )
        for path, sort_key in sliced
    ]
    prepared = materialize_display_slices(slices, 650)
    html = assemble_html(prepared, 650)

    cid_numbers = [int(n) for n in re.findall(r"cid:slice_(\d{3})", html)]
    assert cid_numbers == list(range(1, len(prepared) + 1))
    assert [s.sort_key for s in prepared] == sorted(s.sort_key for s in prepared)


def test_main_does_not_depend_on_pyqt5():
    main_src = (ROOT / "main.py").read_text()
    assert "from PyQt5" not in main_src
    assert "import PyQt5" not in main_src


def test_send_compression_preserves_hotspot_metadata(tmp_path):
    from main import MainWindow, COMPRESS_QUALITY

    p = tmp_path / "mail_part.png"
    make_image(p, 320, 180)
    original = SliceItem(
        path=str(p),
        href="https://button.example",
        alt_text="button",
        sort_key=2.003,
        original_width=650,
    )

    compressed = MainWindow._compress_slice_items(object(), [original])

    assert len(compressed) == 1
    item = compressed[0]
    assert item.path.endswith(".jpg")
    assert f"_q{COMPRESS_QUALITY}_" in item.path
    assert Path(item.path).exists()
    assert item.href == original.href
    assert item.alt_text == original.alt_text
    assert item.sort_key == original.sort_key
    assert item.original_width == original.original_width
    assert original.path.endswith(".png")


def test_send_email_uses_final_slices_for_size_and_compression():
    main_src = (ROOT / "main.py").read_text()
    send_start = main_src.find("def _send_email")
    assert send_start >= 0
    send_body = main_src[send_start:main_src.find("\n    def reset_app", send_start)]

    assert "materialize_display_slices_strict(" in send_body
    assert "estimate_email_size_mb([s.path for s in slices])" in send_body
    assert "self._compress_slice_items(slices)" in send_body
    assert "self._compress_slices()" not in send_body


def test_email_size_estimate_counts_html_overhead_as_kb(tmp_path):
    from image_safety import estimate_email_size_mb

    p = tmp_path / "one.bin"
    p.write_bytes(b"x" * 1024 * 1024)

    # 1MB file + about 3KB HTML overhead still rounds to 1.0MB,
    # not the old incorrect 4.0MB.
    assert estimate_email_size_mb([str(p)]) == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
