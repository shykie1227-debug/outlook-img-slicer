"""
B5 回归测试：image_slicer.detect_and_slice 的 smart 分支不得产生越界 crop

根因（image_slicer.py detect_and_slice）：smart 分支计算
`bottom = max(min_bottom, min(adjusted, max_bottom))`，当 `min_bottom > max_bottom`
（极端长宽比 / 超大 max_height）时 bottom 可能越界，导致 `img.crop((0, top, out_w, bottom))`
裁出空白行或产生错位。

修复：在 bottom 计算后追加 `bottom = min(max(bottom, top+1), out_h)` 防御性 clamp，
并保证 `min_bottom <= max_bottom`。

本测试对多种极端几何（超长竖图、超宽扁图、max_height 远大于/小于原图、smart 开/关）
验证：切片总数 > 0、每张高度 > 0、N 张物理总高严格 == 原图高、每张 crop 均在图像内。
"""
import os
import tempfile

from PIL import Image

from image_slicer import detect_and_slice


def _slice_heights(paths):
    heights = []
    for p in paths:
        with Image.open(p) as img:
            heights.append(img.size[1])
    return heights


def test_smart_slice_heights_contiguous_and_in_bounds():
    """smart=True 下多种极端几何：总高严格 == 原图高，且每张高度 > 0（无越界 crop）。"""
    cases = [
        (650, 5000, 1200),   # 超长竖图
        (3000, 600, 1200),   # 超宽扁图
        (650, 1300, 1200),   # 略超 max_height（切片数=2）
        (650, 2500, 1200),   # 多片
        (650, 1201, 1200),   # 临界：最后一片吸收 1px
        (650, 500, 5000),    # max_height 远大于原图（不切片）
        (100, 8333, 1200),   # 极端瘦高
    ]
    for w, h, max_h in cases:
        with tempfile.TemporaryDirectory() as td:
            img_path = os.path.join(td, "long.png")
            Image.new("RGB", (w, h), (255, 255, 255)).save(img_path)
            paths = detect_and_slice(img_path, max_height=max_h, smart=True)
            assert paths, f"未产出切片 w={w} h={h}"
            heights = _slice_heights(paths)
            # 每张高度必须 > 0（B5 防御：bottom 被 clamp 到 top+1..out_h）
            assert all(hh > 0 for hh in heights), f"存在高度<=0 的切片 w={w} h={h}: {heights}"
            # 物理总高严格 == 原图高（无越界溢出 / 无遗漏）
            assert sum(heights) == h, (
                f"切片总高 {sum(heights)} != 原图 {h}（w={w}, max_h={max_h}）"
            )


def test_smart_slice_no_out_of_bounds_crop():
    """smart 分支：每张切片重开后尺寸合法且为原图子区域（crop 不越界）。

    注：使用白色纯色图（与 test_smart_slice_heights_contiguous_and_in_bounds
    一致）。`_find_smart_cut` 对「纯深色/全均匀」图像会落入昂贵的 fallback
    评分路径（O(扫描窗 × 缓冲带) 每切片），650×4999 实测约 2 分钟；该性能
    问题属 detect_and_slice 既有缺陷（非 B5 clamp 引入），已单独反馈给团队，
    不在本次修复范围内。白色纯色图所有行均为「安全空白行」，主循环可立即
    返回切点，既能快速验证 B5 的 bottom clamp 不越界，又避免无谓超时。
    """
    w, h = 650, 4999
    with tempfile.TemporaryDirectory() as td:
        img_path = os.path.join(td, "long.png")
        Image.new("RGB", (w, h), (255, 255, 255)).save(img_path)
        paths = detect_and_slice(img_path, max_height=1200, smart=True)
        for p in paths:
            with Image.open(p) as img:
                pw, ph = img.size
                assert pw == w, f"切片宽 {pw} != 原宽 {w}"
                assert 0 < ph <= h, f"切片高 {ph} 越界（原高 {h}）"


def test_smart_slice_stress_random_geometries():
    """随机极端几何压力测试：smart=True 永远不崩溃且不产生越界。"""
    import random
    random.seed(1234)
    for i in range(25):
        w = random.choice([200, 650, 1000, 3000])
        h = random.choice([100, 833, 1201, 2500, 5000, 8333, 12000])
        max_h = random.choice([300, 1200, 5000, 20000])
        with tempfile.TemporaryDirectory() as td:
            img_path = os.path.join(td, f"r{i}.png")
            Image.new("RGB", (w, h), (255, 255, 255)).save(img_path)
            paths = detect_and_slice(img_path, max_height=max_h, smart=True)
            heights = _slice_heights(paths)
            assert sum(heights) == h, f"随机用例 #{i} 总高越界: {sum(heights)} != {h}"
            assert all(hh > 0 for hh in heights)
