"""V4.9.2/V4.9.3 plain Outlook stack regression.

After many failed seam fixes, root-cause audit found the key structural
regression from V3.0: the plain long-image path changed from direct consecutive
<img> tags in a single <td> to one nested <div><table><tr><td> wrapper per
slice. Outlook Word can render gaps at those table/block boundaries.

V4.9.2 fixed the HTML structure (back to V3-style direct <img> stack).
V4.9.3 goes further: plain path also skips materialize (which resized
650→652 and rounded heights to 4-multiples) and uses actual image width.

This locks the plain non-hotspot path back to the V3-style structure while
leaving hotspot/multi-segment paths on the richer table layout.
"""

import os
import glob as _glob
import tempfile
from pathlib import Path

from PIL import Image

from html_assembler import SliceItem, assemble_html, generate_plain_html


def _make_slice(path: Path, color: str):
    Image.new("RGB", (650, 400), color).save(path)


def test_plain_send_html_uses_v3_direct_img_stack_without_per_slice_wrappers(tmp_path):
    """V4.9.3: 普通链路不经过 materialize，直接用原始切片生成 HTML。

    验证：
    - 单 <table>/<tr>/<td> 结构（无 per-slice div/table 包裹）
    - img width = 图片实际宽度 (650)，非归一化 652
    - 无 height 属性
    - img style 包含 line-height: 0; font-size: 0;
    """
    paths = []
    for idx, color in enumerate(["red", "green", "blue"], start=1):
        p = tmp_path / f"slice_{idx}.png"
        _make_slice(p, color)
        paths.append(p)

    # V4.9.3: 不调 materialize，直接传原始切片
    raw = [SliceItem(path=str(p), sort_key=float(i), original_width=650) for i, p in enumerate(paths, 1)]
    html = assemble_html(raw, 650)

    assert html.count("<img") == 3
    # One outer table/row/cell only. No per-slice nested tables/div wrappers.
    assert html.count("<table") == 1
    assert html.count("<tr") == 1
    assert html.count("<td") == 1
    assert html.count("<div") == 0
    # V3 proven path: width-only images; no explicit height attributes that Word can round.
    assert 'height="' not in html
    # V4.9.3: width 应为图片实际宽度 650，而非归一化 652
    assert 'width="650"' in html
    assert 'width="652"' not in html
    # V4.9.3: img style 应包含 line-height: 0; font-size: 0;
    assert 'line-height: 0; font-size: 0;' in html
    # CID 引用
    assert 'src="cid:slice_001"' in html
    assert 'src="cid:slice_002"' in html
    assert 'src="cid:slice_003"' in html


def test_plain_copy_html_uses_same_v3_direct_img_stack(tmp_path):
    """V4.9.3: 复制 HTML 路径也跳过 materialize，使用 V3 直接 <img> 堆叠。"""
    paths = []
    for idx, color in enumerate(["red", "green"], start=1):
        p = tmp_path / f"slice_{idx}.png"
        _make_slice(p, color)
        paths.append(p)

    raw = [SliceItem(path=str(p), sort_key=float(i), original_width=650) for i, p in enumerate(paths, 1)]
    html = generate_plain_html(raw, 650)

    assert html.count("<img") == 2
    assert html.count("<table") == 1
    assert html.count("<tr") == 1
    assert html.count("<td") == 1
    assert html.count("<div") == 0
    assert 'height="' not in html
    # V4.9.3: width 应为图片实际宽度 650
    assert 'width="650"' in html
    assert 'width="652"' not in html
    # V4.9.3: img style 应包含 line-height: 0; font-size: 0;
    assert 'line-height: 0; font-size: 0;' in html
    assert "data:image/png;base64," in html


def test_plain_html_no_temp_files_generated(tmp_path):
    """V4.9.3: 普通链路不应产生 materialize 临时文件 (mail_*.png)。"""
    paths = []
    for idx in range(1, 4):
        p = tmp_path / f"slice_{idx}.png"
        _make_slice(p, "red")
        paths.append(p)

    raw = [SliceItem(path=str(p), sort_key=float(i), original_width=650) for i, p in enumerate(paths, 1)]

    # 记录调用前的临时文件
    temp_dir = tempfile.gettempdir()
    before = set(_glob.glob(os.path.join(temp_dir, "mail_*.png")))

    html = assemble_html(raw, 650)

    # 调用后不应有新增的 mail_*.png
    after = set(_glob.glob(os.path.join(temp_dir, "mail_*.png")))
    assert after == before, "普通链路不应产生 materialize 临时文件"
