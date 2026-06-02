"""
Hotspot 物理切割模块（V4.6.6 V1）

核心模型：
  原图 (W, H) + N 个 hotspot
    → 提取每个 hotspot 的 X 范围 (x1, x2)
    → 合并去重 X 切割线（不含 Y 切割线）
    → 切成 K+1 条竖条（每条横跨完整 Y 范围 [0, H]）
    → 每条竖条要么是"普通切片"、要么是"链接切片"（包 <a href>）

V1 限制（架构硬约束）：
  ✗ 仅纵向切割（X 轴），不切横向（Y 轴）
  ✗ 不支持重叠 hotspot（X 范围相交 → 拒绝）
  ✗ 不支持嵌套 hotspot（X 范围包含 → 拒绝）
  ✗ 不支持一个竖条挂多个 URL
  ✗ 不支持 <map>/<area> 兜底
  ✗ 不支持透明覆盖层

V1 优势：
  ✓ Outlook Desktop 100% 可点击（仅用 <a><img></a>）
  ✓ 图上看不到任何标注（hotspot 边界不渲染）
  ✓ 多 hotspot 支持（任意位置）
  ✓ 切割线模型可扩展到 V2（横向 + 网格）
"""
from dataclasses import dataclass
from typing import List, Tuple
from PIL import Image

from clickable_map import Hotspot, HotspotMap


# ── 错误码 ──
class HotspotCutError:
    OVERLAP = "Hotspot X 范围重叠，请勿在已有按钮的横向位置再加新按钮"
    CONTAIN = "Hotspot X 范围被包含于其他 hotspot（嵌套）"
    OUT_OF_BOUNDS = "Hotspot 坐标超出图片范围"
    INVALID_RANGE = "Hotspot 宽度为 0 或负"


@dataclass
class CutStripe:
    """
    一条物理切割出来的"竖条"。

    属性:
      image:    切出来的 PIL Image（RGB）
      x1, x2:   竖条在原图中的 X 范围
      y1, y2:   竖条在原图中的 Y 范围（V1 永远是 [0, H]）
      href:     若该竖条对应某个 hotspot，则为 URL；否则为 None
      hotspot_text:  对应 hotspot 的 text 字段（用于 alt 兜底）
    """
    image: Image.Image
    x1: int
    x2: int
    y1: int
    y2: int
    href: str = None
    hotspot_text: str = ""


def validate_hotspots_no_overlap(
    hotspots: List[Hotspot],
    img_w: int
) -> Tuple[bool, str]:
    """
    V1 重叠检测：检查所有 hotspot 的 X 范围是否相交 / 嵌套。
    严格按"禁止重叠"原则，连相邻擦边都允许（边界相接不算重叠）。

    Args:
        hotspots: 同一图片上的所有 hotspot
        img_w: 原图宽度（用于越界检查）

    Returns:
        (True, "")  通过
        (False, reason)  第一个出错的原因
    """
    if not hotspots:
        return True, ""
    # 1) 越界
    for i, h in enumerate(hotspots):
        if h.x1 < 0 or h.x2 > img_w or h.x1 >= h.x2:
            return False, f"Hotspot #{i + 1}: {HotspotCutError.OUT_OF_BOUNDS or HotspotCutError.INVALID_RANGE}"
    # 2) 重叠 / 嵌套（按 x1 排序后比较相邻）
    sorted_h = sorted(hotspots, key=lambda h: h.x1)
    for i in range(len(sorted_h) - 1):
        a = sorted_h[i]
        b = sorted_h[i + 1]
        # 边界相接不算重叠（a.x2 == b.x1 允许）
        if a.x2 > b.x1:
            return False, HotspotCutError.OVERLAP
    return True, ""


def compute_cut_lines(img_w: int, hotspots: List[Hotspot]) -> List[int]:
    """
    计算 X 切割线：图片左右边 + 每个 hotspot 的 x1, x2。
    去重 + 排序，返回所有切割点（含 0 和 img_w）。

    边界 case: hotspot 太靠近边缘 → x1=0 或 x2=img_w → 正常去重
    """
    lines = {0, img_w}
    for h in hotspots:
        lines.add(h.x1)
        lines.add(h.x2)
    return sorted(lines)


def build_stripe_assignments(
    cut_lines: List[int],
    hotspots: List[Hotspot]
) -> List[Tuple[int, str, str]]:
    """
    给每条竖条（区间）分配 hotspot URL。

    Returns:
        List of (stripe_index, href, text)
        - stripe_index: 竖条在 cut_lines 区间数组中的下标
        - href: 跳转 URL（若无 hotspot 覆盖则为 None）
        - text: 按钮文字
    """
    assignments = {}
    for h in hotspots:
        # 找到包含 h.x1 的区间 (cut_lines[i], cut_lines[i+1])
        for i in range(len(cut_lines) - 1):
            if cut_lines[i] == h.x1:
                # hotspot 的 x1 一定是某条切割线
                assignments[i] = (h.url, h.text)
                break
    return assignments


def slice_image_with_hotspots(
    img: Image.Image,
    hotspots: List[Hotspot]
) -> List[CutStripe]:
    """
    V1 主入口：按 hotspot 的 X 范围纵向切割原图。

    Args:
        img: 原图（PIL Image, RGB）
        hotspots: 用户标注的所有 hotspot

    Returns:
        List[CutStripe]: 从上到下、从左到右的竖条列表
    """
    img_w, img_h = img.size

    # 1) 校验
    ok, reason = validate_hotspots_no_overlap(hotspots, img_w)
    if not ok:
        raise ValueError(reason)

    # 2) 计算切割线
    cut_lines = compute_cut_lines(img_w, hotspots)

    # 3) 分配 hotspot 到对应竖条
    assignments = build_stripe_assignments(cut_lines, hotspots)

    # 4) 物理切割
    stripes: List[CutStripe] = []
    for i in range(len(cut_lines) - 1):
        x1, x2 = cut_lines[i], cut_lines[i + 1]
        # 切割：每条竖条横跨完整 Y
        # box = (left, upper, right, lower) PIL 用法
        stripe_img = img.crop((x1, 0, x2, img_h))
        href, text = assignments.get(i, (None, ""))
        stripes.append(CutStripe(
            image=stripe_img,
            x1=x1, x2=x2,
            y1=0, y2=img_h,
            href=href,
            hotspot_text=text,
        ))
    return stripes


def slice_paths_by_hotspots(
    image_paths: List[str],
    hotspots_by_slice: dict
) -> Tuple[List[str], dict]:
    """
    高级入口：对一组切片路径，按各自的 hotspot 重新物理切割。
    适配 V4.6.5 之前"先按智能切图生成 paths，再对每张 path 标注 hotspot"的流程。

    Args:
        image_paths: 原始切片路径列表
        hotspots_by_slice: {slice_filename: List[Hotspot]}

    Returns:
        (new_paths, link_map)：
        - new_paths: 重新切割后的新切片路径列表
        - link_map: {new_filename: href or None}  记录每张新切片是否带链接
    """
    import os
    from PIL import Image
    new_paths: List[str] = []
    link_map: dict = {}
    base_dir = os.path.dirname(image_paths[0]) if image_paths else "."
    counter = 0
    for path in image_paths:
        fname = os.path.basename(path)
        hots = hotspots_by_slice.get(fname, [])
        with Image.open(path) as img:
            img = img.convert("RGB")
            if not hots:
                # 无 hotspot：原样保留
                new_paths.append(path)
                link_map[fname] = None
                continue
            # 有 hotspot：物理切割
            stripes = slice_image_with_hotspots(img, hots)
            for s in stripes:
                counter += 1
                new_name = f"hs_{counter:03d}.png"
                new_path = os.path.join(base_dir, new_name)
                s.image.save(new_path, "PNG")
                new_paths.append(new_path)
                link_map[new_name] = s.href
    return new_paths, link_map
