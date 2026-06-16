"""
Hotspot 物理切割模块（V4.6.6 V1）

核心模型：
  原图 (W, H) + N 个 hotspot
    → 提取每个 hotspot 的 X 范围 (x1, x2)
    → 合并去重 X 切割线（不含 Y 切割线）
    → 切成 K+1 条竖条（每条横跨完整 Y 范围 [0, H]）
    → 每条竖条要么是"普通切片"、要么是"链接切片"（包 <a href>）

V1 限制（架构硬约束）：
  ✓ V4.8.11 起支持 X/Y 网格切割（上下错开的按钮允许 X 范围重叠）
  ✗ 不支持真实矩形区域重叠 hotspot（面积相交 → 拒绝）
  ✗ 不支持嵌套 hotspot（一个按钮完全包含另一个按钮）
  ✗ 不支持一个网格 cell 挂多个 URL
  ✗ 不支持 <map>/<area> 兜底
  ✗ 不支持透明覆盖层

V1 优势：
  ✓ Outlook Desktop 100% 可点击（仅用 <a><img></a>）
  ✓ 图上看不到任何标注（hotspot 边界不渲染）
  ✓ 多 hotspot 支持（任意位置）
  ✓ V2 横向 + 纵向网格切割
"""
from dataclasses import dataclass
from typing import List, Tuple
from PIL import Image

from clickable_map import Hotspot, HotspotMap


# V4.8.10: 用户手动拖选一排按钮时，1~3px 压线属于正常操作误差。
# 自动吸附边界，避免“多个按钮一排”误报横向重叠。
HOTSPOT_EDGE_SNAP_TOLERANCE_PX = 3


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
    sort_key: float = 0.0  # V4.6.7 排序架构


def validate_hotspots_no_overlap(
    hotspots: List[Hotspot],
    img_w: int,
    img_h: int = None,
) -> Tuple[bool, str]:
    """
    V4.8.11 / V2 重叠检测：只禁止真实矩形区域重叠。

    旧 V1 只按 X 轴纵向切条，因此“上下不同位置但 X 范围重叠”也会报错。
    这是用户连续多版本失败的根因。V2 改为 X/Y 网格切割后，上下错开的按钮
    可以共享同一段 X 范围；只有矩形实际相交才需要阻止。
    """
    if not hotspots:
        return True, ""

    # 1) 越界/无效范围
    for i, h in enumerate(hotspots):
        if h.x1 < 0 or h.x2 > img_w or h.x1 >= h.x2:
            return False, (
                f"Hotspot #{i + 1} 越界或宽度为 0：\n"
                f"  当前：x1={h.x1}, x2={h.x2}（原图宽 {img_w}px）\n"
                f"  要求：0 ≤ x1 < x2 ≤ {img_w}"
            )
        if img_h is not None and (h.y1 < 0 or h.y2 > img_h or h.y1 >= h.y2):
            return False, (
                f"Hotspot #{i + 1} Y 坐标越界或高度为 0：\n"
                f"  当前：y1={h.y1}, y2={h.y2}（原图高 {img_h}px）\n"
                f"  要求：0 ≤ y1 < y2 ≤ {img_h}"
            )

    # 2) 只检查真实矩形相交。上下错开但 X 范围重叠是合法的。
    for i in range(len(hotspots)):
        a = hotspots[i]
        for j in range(i + 1, len(hotspots)):
            b = hotspots[j]
            x_overlap = min(a.x2, b.x2) - max(a.x1, b.x1)
            y_overlap = min(a.y2, b.y2) - max(a.y1, b.y1)
            if x_overlap <= 0 or y_overlap <= 0:
                continue

            # 一排按钮轻微压线：自动吸附水平边界。
            if x_overlap <= HOTSPOT_EDGE_SNAP_TOLERANCE_PX:
                if a.x1 <= b.x1:
                    a.x2 = b.x1
                else:
                    b.x2 = a.x1
                continue

            return False, (
                f"Hotspot #{i + 1} 与 #{j + 1} 实际区域重叠\n\n"
                f"  #{i + 1}: x={a.x1}→{a.x2}, y={a.y1}→{a.y2}\n"
                f"  #{j + 1}: x={b.x1}→{b.x2}, y={b.y1}→{b.y2}\n"
                f"  重叠区域约：{x_overlap}px × {y_overlap}px\n\n"
                f"建议：把其中一个按钮稍微移开，或缩小按钮区域。"
            )
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
    hotspots: List[Hotspot],
    source_index: float = 0.0
) -> List[CutStripe]:
    """
    V4.8.11 / V2 主入口：按 hotspot 的 X/Y 边界网格切割原图。

    V1 只按 X 纵向切条，会导致上下错开的按钮只要 X 范围重叠就报错。
    V2 同时切 X/Y，任何不相交矩形按钮都能共存。
    """
    img_w, img_h = img.size

    # 1) 校验：只禁止真实矩形重叠，不再禁止“上下不同但 X 重叠”
    ok, reason = validate_hotspots_no_overlap(hotspots, img_w, img_h)
    if not ok:
        raise ValueError(reason)

    # 2) 计算 X/Y 网格线
    x_lines = {0, img_w}
    y_lines = {0, img_h}
    for h in hotspots:
        x_lines.add(h.x1)
        x_lines.add(h.x2)
        y_lines.add(h.y1)
        y_lines.add(h.y2)
    x_lines = sorted(x_lines)
    y_lines = sorted(y_lines)

    # 3) 物理切割。sort_key 用 row-major 编码，让 HTML 按 Y 行分组、X 列拼接。
    stripes: List[CutStripe] = []
    for row in range(len(y_lines) - 1):
        y1, y2 = y_lines[row], y_lines[row + 1]
        for col in range(len(x_lines) - 1):
            x1, x2 = x_lines[col], x_lines[col + 1]
            if x1 == x2 or y1 == y2:
                continue
            cell_img = img.crop((x1, y1, x2, y2))
            href, text = None, ""
            for h in hotspots:
                if x1 >= h.x1 and x2 <= h.x2 and y1 >= h.y1 and y2 <= h.y2:
                    href, text = h.url, h.text
                    break
            stripes.append(CutStripe(
                image=cell_img,
                x1=x1, x2=x2,
                y1=y1, y2=y2,
                href=href,
                hotspot_text=text,
                sort_key=source_index + (row + 1) * 0.001 + (col + 1) * 0.000001,
            ))
    return stripes

def slice_paths_by_hotspots(
    image_paths: List[str],
    hotspots_by_slice: dict,
    source_index_map: dict = None
) -> Tuple[List[Tuple[str, float]], dict]:
    """
    高级入口：对一组切片路径，按各自的 hotspot 重新物理切割。

    V4.6.7 排序架构：返回 List[(path, sort_key)]，调用方按 sort_key 排序后输出 HTML。
    **不依赖** append 顺序、文件名、目录遍历、os.listdir 等任何隐式顺序。

    Args:
        image_paths: 原始切片路径列表
        hotspots_by_slice: {slice_filename: List[Hotspot]}
        source_index_map: {slice_filename: source_index}
                          V4.6.7 强制要求调用方传入，避免隐式依赖 path 顺序

    Returns:
        (slices_with_key, link_map)：
        - slices_with_key: List[(path, sort_key)]，调用方须 sorted(..., key=lambda x: x[1])
        - link_map: {filename: href or None}
    """
    import os
    from PIL import Image

    slices_with_key: List[Tuple[str, float]] = []
    link_map: dict = {}
    if not image_paths:
        return slices_with_key, link_map
    base_dir = os.path.dirname(image_paths[0])
    counter = 0  # 文件名唯一性用，不参与排序

    for idx, path in enumerate(image_paths):
        fname = os.path.basename(path)
        if source_index_map is not None and fname in source_index_map:
            source_index = source_index_map[fname]
        else:
            # 兜底：O(1) 枚举索引，避免 O(N) image_paths.index() 性能 + 重复路径 bug
            source_index = float(idx + 1)
        hots = hotspots_by_slice.get(fname, [])
        with Image.open(path) as img:
            img = img.convert("RGB")
            if not hots:
                # 无 hotspot：原切片保留，sort_key = source_index
                slices_with_key.append((path, source_index))
                link_map[fname] = None
                continue
            # 有 hotspot：物理切割，每条竖条 sort_key = source_index + N*0.001
            stripes = slice_image_with_hotspots(img, hots, source_index=source_index)
            for s in stripes:
                counter += 1
                new_name = f"hs_{counter:03d}.png"
                new_path = os.path.join(base_dir, new_name)
                s.image.save(new_path, "PNG")
                slices_with_key.append((new_path, s.sort_key))
                link_map[new_name] = s.href
    return slices_with_key, link_map
