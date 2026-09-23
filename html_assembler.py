"""
HTML 组装器模块（V6.4.0 热点邮件单行列网格 + V4.9.0 缝隙根除）

V6.4.0 变更（当前版本）：
  - 热点邮件结构性根修：整封邮件只有 **1 条 <tr>**、无嵌套表格。
    旧实现（V6.0.3）为每个视觉行输出一条 <tr>，一封 3 按钮邮件实测 9 条 <tr>；
    Outlook Word 引擎在 <tr> 之间始终插入约 1px 间距，行数越多缝隙越多 ——
    这就是"添加可点击按钮后出现各种缝隙"的根因。
    新实现把网格转置：取所有行 X 边界的并集作为列，每列 1 个 <td>，
    列内用 display:block 连续堆叠该列的竖向片段 —— 与普通长图
    （V3.0 用户实测无缝）的写法完全一致，行间缝隙从结构上不存在。
  - materialize 阶段即按"列 × 行"网格产出最终 PNG（SliceItem.grid_col/grid_row），
    PNG 物理尺寸与 HTML 声明严格一致。
  - build_render_plan 与 assemble_html 共用 _ordered_grid_cells（列优先）这一份
    顺序，保证 Outlook 附件 CID 与正文 cid: 引用一一对应不漂移。

V4.9.0 变更：
  - 缝隙根因修：Outlook Word 引擎在多个 <tr> 之间始终插入约 1px 间距。
    改为单 <tr> + 单 <td> 布局，所有图片在同一个 <td> 内通过 <div> 垂直堆叠，
    根除多行之间的 1px 间距。
  - 预渲染重构：用整体缩放替代 _edge_extend_image 边缘扩展。将拼合行缩放到目标
    总尺寸后再切回每段，避免因越界 crop 补黑/补白导致的按钮边界视觉错乱。
  - 移除 _edge_extend_image（V4.8.10 引入）—— 边缘扩展会把相邻竖条的内容混入
    本段，引起按钮错乱。

V4.8.5 缝隙修复：
  - 取消对单组 PNG 高度的"display_w/total_w → 偶数化"缩放。
  - 之前 materialize 会把单组 source_row 从 (display_w, actual_h) resize 到
    (display_w, 偶数化(actual_h * display_w / total_w))，对 833px 这种
    奇数高度会变成 832px，导致声明 height=832 与原始源图差 1px。
  - 3 张普通切片各缩 1px 累计产生肉眼可见的"每片切图衔接处有缝"。
  - 偶数化策略已收敛为统一的 _even_pixel_4x（4 的倍数），其余 2x/2x-up 旧函数已删除（B6）。

V4.7.8 优化点：
  - 优化图片尺寸缓存，减少重复读取
  - 进一步加强 Outlook 缝隙消除（mso-padding-alt, mso-border-alt）
  - 优化多按钮横向拼接宽度分配，避免错位
  - 加强偶数像素约束，防止 px->pt 转换产生小数

V1 架构变更：
  - 不再使用 Hotspot Map（图上标注 + 物理切割已在 hotspot_slicer.py 完成）
  - 不再输出 <map> + <area>（Outlook Desktop 不解析，删）
  - 不再输出图外 CTA 文字链接行
  - 接受 List[SliceItem]，每项包含 (path, href)

Outlook 兼容性（第一目标 = Outlook Desktop / Word 引擎）：
  ✓ 仅用 <table> + inline-style
  ✓ <a><img></a> 是最基础 HTML，所有 Outlook 客户端可点
  ✓ width + height HTML 属性（不用 CSS）
  ✓ border="0" + style="display:block;" 消除图片间 1px 间隙
  ✓ cellpadding="0" cellspacing="0" border="0" 消除 cell 间隙
  ✓ 单 <tr> + 单 <td> 布局，根除行间 1px 间距
"""
from pathlib import Path
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
from html import escape
import os
import uuid
from PIL import Image

# V4.7.8: 图片尺寸缓存，避免重复读取同一文件
_img_dimensions_cache: Dict[str, Tuple[int, int]] = {}

# V4.8.7: materialize 临时文件追踪 — 调用方负责删除
# 每次 materialize_display_slices_strict 调用追加新文件，调用方用 cleanup_temp_slices 删
_materialized_temp_files: List[str] = []


def _track_temp_files(paths: List[str]) -> List[str]:
    """登记本次 materialize 产生的临时文件，返回同一列表便于链式调用。"""
    _materialized_temp_files.extend(paths)
    return paths


def cleanup_temp_slices(paths: List[str]) -> int:
    """
    删除 materialize 产生的临时 PNG 切片，best-effort。

    Args:
        paths: 要删除的文件路径列表

    Returns:
        成功删除的数量
    """
    deleted = 0
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
                deleted += 1
        except OSError:
            pass
    return deleted


def cleanup_all_tracked_temp_slices() -> int:
    """进程退出兜底：删掉本进程所有 materialize 临时文件。"""
    return cleanup_temp_slices(list(_materialized_temp_files))


@dataclass
class SliceItem:
    """
    一张物理切片 + 是否带链接 + sort_key。
    hotspot_slicer.py 的输出直接转成 List[SliceItem]。

    V4.6.7 排序架构：
      - sort_key 是 HTML 输出的唯一排序依据
      - **不依赖** append 顺序、文件名、os.listdir、目录遍历
      - HTML 输出前须 sorted(slices, key=lambda s: s.sort_key)
      - 原切片 sort_key = source_index（整数 1.0, 2.0, 3.0, ...）
      - Hotspot 派生竖条 sort_key = source_index + N*0.001

    V4.6.9：加 original_width 字段，记录**该切片所属原图**的宽度。
    V1 物理切割后，链接竖条只是原图一部分 X 范围。
    HTML 输出时，每段需按 actual_w / original_w 比例分配 display_w，
    否则多段拼起来 = 原图宽 × N倍 ＝ 邮件里**图被拉伸错乱**。
    """
    path: str
    href: Optional[str] = None
    alt_text: str = ""
    sort_key: float = 0.0
    # V4.6.9 修复：原图宽度，用于多段拼接时按比例缩放
    original_width: int = 0
    # V6.4.0 单行列网格：materialize 产出的最终网格单元坐标。
    # grid_col/grid_row >= 0 表示该切片已是「单行列网格」单元，
    # HTML 侧据此直接输出 1 条 <tr>（列 = <td>，行 = <td> 内堆叠 <img>）。
    grid_col: int = -1
    grid_row: int = -1


@dataclass(frozen=True)
class MailRenderItem:
    """Final immutable geometry shared by HTML generation and Outlook CID attachment order."""

    path: str
    href: Optional[str]
    alt_text: str
    sort_key: float
    physical_width: int
    physical_height: int
    display_width: int
    display_height: int
    cid: str


@dataclass(frozen=True)
class MailRenderPlan:
    display_width: int
    items: Tuple[MailRenderItem, ...]


def build_render_plan(slices: List[SliceItem], display_w: int = 650) -> MailRenderPlan:
    """Create the canonical ordered geometry used by the final email."""
    ordered = sorted(slices, key=lambda item: item.sort_key)
    groups = _group_by_source(ordered)
    if _is_plain_vertical_stack(groups):
        render_items = []
        effective_width = 0
        for index, item in enumerate(ordered, start=1):
            physical_width, physical_height = _get_img_dimensions(item.path)
            if effective_width == 0:
                effective_width = physical_width
            render_items.append(MailRenderItem(
                path=item.path,
                href=item.href,
                alt_text=item.alt_text,
                sort_key=item.sort_key,
                physical_width=physical_width,
                physical_height=physical_height,
                display_width=physical_width,
                display_height=physical_height,
                cid=f"slice_{index:03d}",
            ))
        return MailRenderPlan(effective_width or int(display_w), tuple(render_items))

    if _is_single_row_grid(slices):
        # V6.4.0：切片已是最终网格单元，几何尺寸直接读 PNG（materialize 已保证
        # 物理尺寸 == 声明尺寸）。CID 编号顺序必须与 HTML 的 <td> 顺序一致（列优先）。
        cells = _ordered_grid_cells(slices)
        column_widths: Dict[int, int] = {}
        for item in cells:
            width, _height = _get_img_dimensions(item.path)
            column_widths.setdefault(item.grid_col, width)
        plan_width = sum(column_widths[col] for col in sorted(column_widths))
        render_items = []
        for index, item in enumerate(cells, start=1):
            physical_width, physical_height = _get_img_dimensions(item.path)
            render_items.append(MailRenderItem(
                path=item.path,
                href=item.href,
                alt_text=item.alt_text,
                sort_key=item.sort_key,
                physical_width=physical_width,
                physical_height=physical_height,
                display_width=physical_width,
                display_height=physical_height,
                cid=f"slice_{index:03d}",
            ))
        return MailRenderPlan(plan_width, tuple(render_items))

    widths_by_path: Dict[str, int] = {}
    heights_by_path: Dict[str, int] = {}
    for group in groups:
        widths = _allocate_group_widths(group, display_w)
        height = _compute_group_height(group, display_w)
        for item in group:
            widths_by_path[item.path] = widths[item.path]
            heights_by_path[item.path] = height

    render_items = []
    for index, item in enumerate(ordered, start=1):
        physical_width, physical_height = _get_img_dimensions(item.path)
        render_items.append(MailRenderItem(
            path=item.path,
            href=item.href,
            alt_text=item.alt_text,
            sort_key=item.sort_key,
            physical_width=physical_width,
            physical_height=physical_height,
            display_width=widths_by_path[item.path],
            display_height=heights_by_path[item.path],
            cid=f"slice_{index:03d}",
        ))
    return MailRenderPlan(_normalize_display_width(display_w), tuple(render_items))


def _get_img_dimensions(img_path: str) -> tuple:
    """
    获取图片实际像素尺寸 (width, height)。
    V4.7.8: 使用缓存，避免重复读取同一文件。
    """
    if img_path in _img_dimensions_cache:
        return _img_dimensions_cache[img_path]
    with Image.open(img_path) as img:
        dims = img.size
        _img_dimensions_cache[img_path] = dims
        return dims


def _clear_dimensions_cache():
    """
    清除图片尺寸缓存（释放内存）。
    每次完整生成 HTML 后调用。
    """
    global _img_dimensions_cache
    _img_dimensions_cache.clear()


def _even_pixel_4x(n: int) -> int:
    """
    V4.8.8: 向上取 4 的倍数。
    Outlook Word 引擎 px→pt 转换: 1px = 0.75pt。
    只有 4 的倍数 px 才能产生整数 pt (4px = 3pt)。
    非 4 倍数的 px 产生 0.5pt 或 0.25pt 小数，
    Word 四舍五入后出现 1px 白线 — 这是 V4.8.2~V4.8.7 缝隙的真正根因。
    833px → 836px (627.0pt 整数) 而非 834px (625.5pt 半点小数)。
    """
    if n <= 1:
        return max(4, ((n + 3) // 4) * 4)
    remainder = n % 4
    if remainder == 0:
        return n
    return n + (4 - remainder)


def _normalize_display_width(display_w: int) -> int:
    """
    统一邮件显示宽度。
    V4.8.8: 强制 4 的倍数。Outlook px→pt 转换 (1px=0.75pt)，
    只有 4 的倍数产生整数 pt，消除 1px 白线。
    """
    try:
        value = int(display_w)
    except (TypeError, ValueError):
        value = 648  # 默认 648 = 4 的倍数 = 486pt
    return _even_pixel_4x(max(1, value))


def _distribute_units(raw: List[float], total_units: int) -> List[int]:
    """按最大余数法把 total_units 分配给每段，每段至少 1 个单位。

    B1 防护：当 remainder<0 且所有 units 都已 ==1 时，原 while 循环无法再减，
    会无限自增 idx 造成死循环。这里加两层 guard：
      1) 单轮若没有任何分支执行（progress_made 为 False）→ 立即停止；
      2) 迭代次数超过上限（max_iter）→ 停止。
    停止后若 remainder 仍非 0（如 total_units < 段数，本就不可能每段>=1），
    退化为「尽量均分、末段吃余数」的确定性结果，保证 sum == total_units、不挂起。
    """
    if not raw:
        return []
    units = [max(1, int(v)) for v in raw]
    remainder = total_units - sum(units)
    if remainder == 0:
        return units
    fractions = sorted(
        range(len(raw)),
        key=lambda i: raw[i] - int(raw[i]),
        reverse=(remainder > 0),
    )
    # B1: 迭代上限 = 每段最多调整 |remainder| 次 + 容差；超出视为无法收敛。
    max_iter = len(raw) * (abs(remainder) + 1) + 8
    idx = 0
    iteration = 0
    progress_made = True
    while remainder != 0 and fractions and iteration < max_iter and progress_made:
        progress_made = False
        target = fractions[idx % len(fractions)]
        if remainder > 0:
            units[target] += 1
            remainder -= 1
            progress_made = True
        elif units[target] > 1:
            units[target] -= 1
            remainder += 1
            progress_made = True
        idx += 1
        iteration += 1
    # 退化兜底：保证返回值之和严格等于 total_units（极端窄 cell 场景）。
    if remainder != 0:
        n = len(units)
        if n == 0:
            return []
        base = max(0, total_units // n)
        rem = total_units - base * n
        units = [base + (1 if i < rem else 0) for i in range(n)]
    return units


def _allocate_axis_4x(source_lengths: List[int], target_total: int) -> List[int]:
    """Map source boundaries to 4px Outlook units while preserving one total size."""
    if not source_lengths or any(length <= 0 for length in source_lengths):
        raise ValueError("invalid source geometry")
    target_total = _even_pixel_4x(target_total)
    total_units = target_total // 4
    if total_units < len(source_lengths):
        raise ValueError("too many hotspot partitions for the target size")
    source_total = sum(source_lengths)
    raw_units = [length * total_units / source_total for length in source_lengths]
    return [units * 4 for units in _distribute_units(raw_units, total_units)]


def _build_cell(slice_path: str, cid_or_src: str, display_w: int, href: Optional[str] = None,
              alt: str = "", original_width: int = 0, is_base64: bool = False,
              forced_display_w: Optional[int] = None,
              forced_display_h: Optional[int] = None,
              colspan: int = 1) -> str:
    """
    生成一张切片的 <td>...</td>（V4.7.8 缝隙消除+错位修复）。

    V4.7.8 优化点：
      - 进一步加强 Outlook 缝隙消除（mso-line-height-rule 强制）
      - 所有尺寸严格偶数化
      - 添加 mso-table-lspace/mso-table-rspace 相关属性

    拆 _build_image_row 的原因：
      之前每段占一整 <tr> → 纵向堆叠 → V1 物理切割产物重叠成
      "碎片化"视觉。现在改为同 source_index 的多段拼成一行 <tr>，
      每段 1 个 <td> 横向并排，恢反原图。

    Args:
        cid_or_src: 若是 base64 模式（复制到剪贴板）则传 data:xxx；CID 模式传 cid:xxx
        is_base64: True = generate_plain_html 路径，False = assemble_html 路径
    """
    try:
        actual_w, actual_h = _get_img_dimensions(slice_path)
    except Exception:
        actual_w, actual_h = 650, 650

    display_w = _normalize_display_width(display_w)
    if forced_display_w is not None:
        seg_display_w = _even_pixel_4x(max(1, int(forced_display_w)))
    elif original_width > 0 and actual_w > 0:
        ratio = actual_w / original_width
        seg_display_w = _even_pixel_4x(round(display_w * ratio))
    else:
        seg_display_w = _even_pixel_4x(display_w)
    # V4.8.8: forced_display_h 已由 _compute_group_height 算好（4 的倍数），
    # 直接用，不再二次处理。
    if forced_display_h is not None:
        seg_display_h = max(1, int(forced_display_h))
    else:
        raw_h = round(actual_h * seg_display_w / actual_w) if actual_w else 650
        seg_display_h = _even_pixel_4x(raw_h)

    if not alt:
        alt = Path(slice_path).name
    safe_alt = escape(alt, quote=True)

    # base64 模式 vs CID 模式
    if is_base64:
        import base64
        with open(slice_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        ext = Path(slice_path).suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        src = f"data:{mime};base64,{b64}"
    else:
        src = cid_or_src
    safe_src = escape(src, quote=True)

    img_tag = (
        f'<img src="{safe_src}" '
        f'width="{seg_display_w}" '
        f'height="{seg_display_h}" '
        f'alt="{safe_alt}" '
        f'border="0" hspace="0" vspace="0" '
        f'style="width: {seg_display_w}px; height: {seg_display_h}px; '
        f'border: 0; border-collapse: collapse; border-spacing: 0; '
        f'display: block; outline: none; text-decoration: none; '
        f'vertical-align: top; margin: 0; padding: 0; '
        f'line-height: 0; font-size: 0; '
        f'-ms-interpolation-mode: bicubic;" />'
    )

    if href:
        safe_href = escape(href, quote=True)
        inner = (
            f'<a href="{safe_href}" target="_blank" '
            f'style="display: block; width: {seg_display_w}px; height: {seg_display_h}px; '
            f'text-decoration: none; outline: none; border: 0; border-collapse: collapse; '
            f'mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px; '
            f'line-height: 0; font-size: 0;">'
            f'{img_tag}'
            f'</a>'
        )
    else:
        inner = img_tag

    colspan_attr = f' colspan="{colspan}"' if colspan > 1 else ""
    return (
        f'<td align="left" valign="top" width="{seg_display_w}" height="{seg_display_h}"'
        f'{colspan_attr} style="'
        f'width: {seg_display_w}px; height: {seg_display_h}px; '
        f'padding: 0; margin: 0; border: 0; border-collapse: collapse; border-spacing: 0; '
        f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
        f'vertical-align: top; mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px; '
        f'mso-text-raise: 0;'
        f'">'
        f'{inner}'
        f'</td>\n'
    )


def _build_image_row(slice_path: str, cid: str, display_w: int, href: Optional[str] = None, alt: str = "",
                    original_width: int = 0) -> str:
    """
    兼容旧 API：返回 <tr><td>...</td></tr>。
    V4.6.9 后推荐使用 _build_cell + 手工拼 <tr>（见 assemble_html）。
    """
    return (
        f'<tr>\n'
        f'{_build_cell(slice_path, cid, display_w, href, alt, original_width)}'
        f'</tr>\n'
    )


def _is_plain_vertical_stack(groups: List[List[SliceItem]]) -> bool:
    """
    普通长图链路：每个视觉组只有一张、无 href 的切片。

    V3.0 用户实测无缝的结构是：一个 <td> 里直接连续 <img>。
    V4.6+ 为 hotspot 重组引入每片外层 <div><table><tr><td>，普通链路也被套进去，
    这是 Outlook Word 引擎在切片之间插入缝隙的最高嫌疑结构差异。
    """
    if not groups:
        return False
    for group in groups:
        if len(group) != 1:
            return False
        if group[0].href:
            return False
    return True


def _is_single_row_grid(slices: List[SliceItem]) -> bool:
    """
    V6.4.0：切片是否已经是「单行列网格」的最终网格单元（由 materialize 产出）。

    判定依据是 SliceItem.grid_col/grid_row >= 0，而不是猜 sort_key 编码，
    避免与 V1/V2 hotspot 编码混淆。
    """
    if not slices:
        return False
    return all(s.grid_col >= 0 and s.grid_row >= 0 for s in slices)


def _ordered_grid_cells(slices: List[SliceItem]) -> List[SliceItem]:
    """
    单行列网格的输出顺序：列优先（与 HTML 里 <td> 的排列顺序一致）。

    build_render_plan 的 CID 编号和 assemble_html 的 cid 引用都必须用这个顺序，
    否则 Outlook 附件 CID 与正文引用错位，图片会整体错乱。
    """
    return sorted(slices, key=lambda item: (item.grid_col, item.grid_row))


def _build_v3_plain_image_stack(groups: List[List[SliceItem]], display_w: int,
                                is_base64: bool = False) -> Tuple[str, int]:
    """
    V3-style 普通纵向堆叠：一个 td 内连续 block img。
    不产生每片 div/table/tr/td 边界；避免 Outlook Word 在块/表格边界制造白缝。

    V4.9.3 变更：
      - 使用图片实际宽度而非归一化 display_w，消除 650→652 拉伸
      - img style 补充 line-height: 0; font-size: 0; 防 Outlook 行间距
      - 移除 min-height: 1px（V3.0 原始版本无此属性）

    V6.0.2 回滚 V6.0.1：
      - 移除 height HTML 属性和 style 中的 height
      - 原因：Outlook Word 引擎 px→pt 转换 (1px=0.75pt)，非 4 的倍数高度
        会产生小数 pt，Word 四舍五入后导致图片间 1px 错位，多片累积为可见偏移
      - V3.0 验证过的稳定方案：只写 width，让 Outlook 按宽高比自动计算 height
    """
    img_tags = ""
    cid_counter = 0
    for group in groups:
        s = group[0]
        try:
            actual_w, actual_h = _get_img_dimensions(s.path)
            img_w = actual_w if actual_w > 0 else display_w
        except Exception:
            img_w = display_w

        if is_base64:
            import base64
            with open(s.path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            ext = Path(s.path).suffix.lower().lstrip(".")
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
            src = f"data:{mime};base64,{b64}"
        else:
            cid_counter += 1
            src = f"cid:slice_{cid_counter:03d}"
        safe_src = escape(src, quote=True)
        safe_alt = escape(s.alt_text or Path(s.path).name, quote=True)
        img_tags += (
            f'<img src="{safe_src}" '
            f'width="{img_w}" '
            f'alt="{safe_alt}" '
            f'border="0" hspace="0" vspace="0" '
            f'style="display: block; width: {img_w}px; '
            f'border: 0; outline: none; text-decoration: none; '
            f'margin: 0; padding: 0; '
            f'line-height: 0; font-size: 0; '
            f'vertical-align: top; -ms-interpolation-mode: bicubic; '
            f'visibility: visible !important;" />'
        )
    return img_tags, cid_counter


def _group_by_source(slices: List[SliceItem]) -> List[List[SliceItem]]:
    """
    按视觉行分组。

    V4.6.9: 旧版按 sort_key 整数部分（source_index）分组，同一原图所有 hotspot
    竖条拼成一行。

    V4.8.11: hotspot V2 改为 X/Y 网格切割，sort_key 编码为：
      source_index + row*0.001 + col*0.000001
    因此同一原图必须按 row 分成多行，每行内部再按 col 横向拼接。
    否则所有网格 cell 会被错误拼成一个超宽横排。

    V5.0.1: 兼容 V1 hotspot 编码 (source_index + N*0.001)，
    识别方式：如果切片没有 col 编码（百万分位为 0），按 V1 编码把
    N*0.001 视为同一行的列，不再拆成多行。
    """
    sorted_slices = sorted(slices, key=lambda s: s.sort_key)
    groups: List[List[SliceItem]] = []
    current_group: List[SliceItem] = []
    current_key = None
    for s in sorted_slices:
        src_idx = int(s.sort_key)
        frac = max(0.0, s.sort_key - src_idx)
        # 百万分位：V2 hotspot 网格的 col 编码；V1 无此编码
        col_frac = frac - int(frac * 1000 + 1e-6) / 1000
        if abs(col_frac) < 1e-7:
            # V1 hotspot 或普通切片：row=0，按 source_index 合并
            row_idx = 0
        else:
            # V2 网格：row 编码在千分位
            row_idx = int(frac * 1000 + 1e-6)
        key = (src_idx, row_idx)
        if current_key is None or key != current_key:
            if current_group:
                groups.append(current_group)
            current_group = [s]
            current_key = key
        else:
            current_group.append(s)
    if current_group:
        groups.append(current_group)
    return groups


def _allocate_group_widths(group: List[SliceItem], display_w: int) -> Dict[str, int]:
    """
    V4.7.8 优化版：为同一原图的横向分段分配显示宽度，保证总和严格等于 display_w。

    Outlook 的 Word 引擎对表格宽度非常敏感。逐段 round() 可能让一行总宽
    变成 display_w±1px，实际发送时容易被重排或换行，表现为标注切片错位。

    V4.7.8 优化：
      - 首先确保 display_w 是偶数
      - 偶数化每一段宽度后，精确调整最后一段保持总和
    """
    if not group:
        return {}
    if len(group) == 1:
        return {group[0].path: _normalize_display_width(display_w)}

    # V4.7.8: 先确保目标显示宽度是偶数
    target_w = _normalize_display_width(display_w)

    dims: List[Tuple[SliceItem, int]] = []
    for s in group:
        try:
            actual_w, _ = _get_img_dimensions(s.path)
        except Exception:
            actual_w = 0
        dims.append((s, actual_w))

    total_actual_w = sum(w for _, w in dims if w > 0)
    if total_actual_w <= 0:
        weights = [1.0] * len(group)
    else:
        weights = [max(1, w) / total_actual_w for _, w in dims]

    # V4.8.8: 优先按 4px 单位分配，保证每段、总宽都是 4 的倍数，
    # 避免 Outlook px→pt 小数白线。
    # 如果段数极端多到 4px 都分不下，退回 2px 单位，最后退回 1px。
    if target_w // 4 >= len(group):
        total_units = target_w // 4
        raw_units = [weight * total_units for weight in weights]
        even_widths = [u * 4 for u in _distribute_units(raw_units, total_units)]
    elif target_w // 2 >= len(group):
        total_units = target_w // 2
        raw_units = [weight * total_units for weight in weights]
        even_widths = [u * 2 for u in _distribute_units(raw_units, total_units)]
    else:
        raw_pixels = [weight * target_w for weight in weights]
        even_widths = _distribute_units(raw_pixels, target_w)

    diff = target_w - sum(even_widths)
    if diff and even_widths:
        even_widths[-1] = max(1, even_widths[-1] + diff)

    return {s.path: w for (s, _), w in zip(dims, even_widths)}


def _compute_group_height(group: List[SliceItem], display_w: int) -> int:
    """
    同一原图的横向分段必须使用同一个显示高度，避免 Outlook 中上下错位。

    V4.7.7: 输出强制偶数（Outlook px→pt 转换无小数 → 消除 1px 白线）。
    V4.8.5: 单组（len(group)==1）改为向上偶数化 actual_h。
    V4.8.8: 单组改用 _even_pixel_4x（4 的倍数），因为 2 的倍数中有一半
      不是 4 的倍数，产生 0.5pt 小数 → Word 四舍五入 → 白线。
      例：833px → _even_pixel_up=834 (625.5pt ❌) → _even_pixel_4x=836 (627.0pt ✅)
      多组仍走统一 row_height 计算（多段必须共享 row_h），并对齐 4 的倍数。
    """
    display_w = _normalize_display_width(display_w)

    # V4.8.8: 单组走"4 的倍数"路径
    if len(group) == 1:
        try:
            _, actual_h = _get_img_dimensions(group[0].path)
        except Exception:
            return _even_pixel_4x(display_w)
        if actual_h > 0:
            return _even_pixel_4x(actual_h)
        return _even_pixel_4x(display_w)

    total_w = 0
    row_h = 0
    for s in group:
        try:
            actual_w, actual_h = _get_img_dimensions(s.path)
        except Exception:
            continue
        if actual_w > 0:
            total_w += actual_w
            row_h = max(row_h, actual_h)
    if total_w <= 0 or row_h <= 0:
        return _even_pixel_4x(display_w)
    # V4.8.8: 多组也改用 4 的倍数
    return _even_pixel_4x(max(1, round(row_h * display_w / total_w)))


# NOTE: 以下旧结构已删除：
# - _build_group_row / _build_inline_segment（B3/B4 死代码，Fix 1-A / Fix 2-C）。
# - _build_complex_inline_stack（V6.0.3 单表多 <tr> 版本，V6.4.0 被
#   _build_single_row_column_grid 取代）：它为每个视觉行输出一条 <tr>，
#   一封 3 按钮邮件实测 9 条 <tr>；Outlook Word 引擎在 <tr> 之间始终插入约 1px
#   间距，行数越多缝隙越多 —— 这是"添加可点击按钮后出现各种缝隙"的根因。
# - _build_cell / _build_image_row：只被上述两条旧链路使用，一并删除。


def _grid_cell_image(slice_path: str, src: str, width: int, height: int,
                     href: Optional[str], alt: str, is_base64: bool) -> str:
    """
    生成一个网格单元的 <img>（或 <a><img></a>）。

    写法对齐 _build_v3_plain_image_stack（普通长图已验证无缝的同一套属性）：
    display:block + font-size:0 + line-height:0 + vertical-align:top。
    """
    if is_base64:
        import base64
        with open(slice_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        ext = Path(slice_path).suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
        src = f"data:{mime};base64,{b64}"
    safe_src = escape(src, quote=True)
    safe_alt = escape(alt or Path(slice_path).name, quote=True)
    img_tag = (
        f'<img src="{safe_src}" '
        f'width="{width}" height="{height}" '
        f'alt="{safe_alt}" '
        f'border="0" hspace="0" vspace="0" '
        f'style="width: {width}px; height: {height}px; '
        f'border: 0; border-collapse: collapse; border-spacing: 0; '
        f'display: block; outline: none; text-decoration: none; '
        f'vertical-align: top; margin: 0; padding: 0; '
        f'line-height: 0; font-size: 0; '
        f'-ms-interpolation-mode: bicubic; '
        f'visibility: visible !important;" />'
    )
    if href:
        safe_href = escape(href, quote=True)
        return (
            f'<a href="{safe_href}" target="_blank" '
            f'style="display: block; width: {width}px; height: {height}px; '
            f'text-decoration: none; outline: none; border: 0; '
            f'border-collapse: collapse; border-spacing: 0; '
            f'mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px; '
            f'line-height: 0; font-size: 0;">{img_tag}</a>'
        )
    return img_tag


def _build_single_row_column_grid(slices: List[SliceItem], display_w: int,
                                  is_base64: bool = False,
                                  cid_by_sort_key: Optional[Dict[float, str]] = None) -> str:
    """
    V6.4.0 单行列网格：整封邮件只有 **1 条 <tr>**，每列 1 个 <td>，列内连续堆叠 <img>。

    返回的是 `<td>...</td>` 序列，直接放进外层 <table> 的唯一 <tr> 里 ——
    不再产生嵌套表格。这是普通长图（V3.0 实测无缝）与热点邮件在结构上的统一：

      普通长图  ：<table><tr><td> img img img </td></tr></table>
      热点邮件  ：<table><tr><td> img img </td><td> img </td>...</td></tr></table>

    唯一差异是普通长图只有 1 个 <td>；纵向堆叠写法完全一致，因此
    行间 1px 缝从结构上不存在。横向为同一 <tr> 内的相邻 <td>，
    由 border-collapse + cellspacing=0 + table-layout:fixed 保证无缝。
    """
    display_w = _normalize_display_width(display_w)
    columns: Dict[int, List[SliceItem]] = {}
    for item in slices:
        columns.setdefault(item.grid_col, []).append(item)

    cells = ""
    for col_index in sorted(columns):
        column = sorted(columns[col_index], key=lambda item: item.grid_row)
        dimensions = [_get_img_dimensions(item.path) for item in column]
        column_widths = {width for width, _height in dimensions}
        if len(column_widths) != 1:
            raise ValueError("hotspot grid column width is not consistent")
        col_width = column_widths.pop()
        total_height = sum(height for _width, height in dimensions)

        inner = ""
        for item, (_width, height) in zip(column, dimensions):
            if is_base64:
                src = ""
            else:
                # cid_by_sort_key 里存的是裸 CID（与 build_render_plan /
                # resolve_attachment_manifest 一致），写进 HTML 时必须补 cid: 前缀。
                bare_cid = (cid_by_sort_key or {}).get(item.sort_key, "")
                if not bare_cid:
                    raise ValueError("missing cid for hotspot grid cell")
                src = f"cid:{bare_cid}"
            inner += _grid_cell_image(
                item.path, src, col_width, height, item.href, item.alt_text, is_base64
            )

        cells += (
            f'<td align="left" valign="top" width="{col_width}" '
            f'style="width: {col_width}px; height: {total_height}px; '
            f'padding: 0; margin: 0; border: 0; border-collapse: collapse; border-spacing: 0; '
            f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
            f'vertical-align: top; mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px; '
            f'mso-text-raise: 0;">\n'
            f'{inner}'
            f'</td>\n'
        )

    if not cells:
        raise ValueError("hotspot grid produced no cells")
    total_width = sum(
        _get_img_dimensions(column[0].path)[0]
        for _col_index, column in sorted(columns.items())
    )
    if total_width != display_w:
        raise ValueError(
            f"hotspot grid column widths sum to {total_width}, expected {display_w}"
        )
    return cells


def materialize_display_slices(slices: List[SliceItem], display_w: int = 650) -> List[SliceItem]:
    """
    生成一组"最终显示尺寸"的临时切片。

    V5.0.2 重构（消除段间 1px 缝 + 视觉宽度统一）：
    旧实现对单段切片独立缩放，LANCZOS 舍入误差导致最后一段少 1px，
    段间出现 1px 白线，且各原图独立缩放比例可能不一致。

    新实现：
    - 单段（普通切片）：按 original_width 等比缩放到 display_w_even
    - 多段（hotspot 行）：横向拼合 + 整体缩放 + 切回（不变）
    - V5.0.2 新增：把同一 source_index 的所有单段切片聚合，拼成完整长图
      一次性缩放后按比例切回，最后一段吃余数（消除 1px 缝 + 视觉宽度严格统一）

    注：单 source_index 内的所有段共享 original_width，且通常来自同一原图。
    """
    if not slices:
        return []

    display_w_even = _normalize_display_width(display_w)

    # V5.0.2: 按 (source_index, hotspot_row) 分组聚合
    # - 纯普通切片（frac=0）：按 source_index 聚合
    # - V1/V2 hotspot 切条：按 (source_index, row) 聚合（每行一组）
    by_source_plain: dict = {}
    hotspot_rows_map: dict = {}  # (src_idx, row_idx) -> [slices]

    sorted_slices = sorted(slices, key=lambda s: s.sort_key)
    for s in sorted_slices:
        src_idx = int(s.sort_key)
        frac = s.sort_key - src_idx
        col_frac = frac - int(frac * 1000 + 1e-6) / 1000
        if abs(frac) < 1e-7:
            # 纯普通切片（无 hotspot 切条）：按 source_index 聚合
            by_source_plain.setdefault(src_idx, []).append(s)
        else:
            # hotspot 切条：按 (source_index, row) 分组
            row_idx = int(frac * 1000 + 1e-6)
            key = (src_idx, row_idx)
            hotspot_rows_map.setdefault(key, []).append(s)

    prepared: List[SliceItem] = []
    out_dir = Path(slices[0].path).parent
    batch = uuid.uuid4().hex[:8]
    counter = 0

    # 1. 处理纯普通切片：按 source_index 聚合，整体缩放后切回
    for src_idx in sorted(by_source_plain.keys()):
        seg_list = by_source_plain[src_idx]
        try:
            # 读取所有段的 actual 尺寸
            segs = []
            for s in seg_list:
                with Image.open(s.path) as img:
                    part = img.convert("RGB")
                    segs.append((s, part.copy(), part.width, part.height))
            if not segs:
                continue
            # 推断原图总宽：取所有段的 original_width 最大值
            orig_w = max((getattr(s, 'original_width', 0) or 0) for s, _, _, _ in segs) or segs[0][2]
            # 单段原图宽度如果都和 actual_w 一致，用 actual_w
            if all(p_w == orig_w for _, _, p_w, _ in segs):
                # 所有段都来自同一原图
                total_h = sum(p_h for _, _, _, p_h in segs)
                scale = display_w_even / orig_w if orig_w != display_w_even else 1.0
                target_w = display_w_even if scale != 1.0 else orig_w
                # V5.0.2: 先算精确总高，再向上 4 倍数化
                target_total_h = _even_pixel_4x(int(total_h * scale + 0.999))
                # 拼成完整长图
                full = Image.new("RGB", (orig_w, total_h))
                y = 0
                for _, part, _, p_h in segs:
                    full.paste(part, (0, y))
                    y += p_h
                # 缩放（如果需要）并补齐到 target_total_h
                if scale != 1.0:
                    full_resized = full.resize((target_w, target_total_h), Image.LANCZOS)
                else:
                    # V5.0.2: scale=1.0 时也需要补齐高度到 target_total_h（4 的倍数）
                    # 避免 row_height (836) > actual_h (833) 时裁剪超界
                    if total_h < target_total_h:
                        full_resized = Image.new("RGB", (orig_w, target_total_h))
                        full_resized.paste(full, (0, 0))
                        # 底部延展最后一行像素（与 _compute_group_height 行为一致）
                        last_row = full.crop((0, total_h - 1, orig_w, total_h))
                        for yy in range(total_h, target_total_h):
                            full_resized.paste(last_row, (0, yy))
                    else:
                        full_resized = full
                # 按比例切回，最后一段吃余数
                crop_y = 0
                for i, (s, _, _, p_h) in enumerate(segs):
                    counter += 1
                    if i == len(segs) - 1:
                        # 最后一段：吃余数
                        seg_h = target_total_h - crop_y
                    else:
                        seg_h = _even_pixel_4x(int(p_h * scale + 0.999))
                    target_path = out_dir / f"mail_{batch}_{counter:03d}.png"
                    part = full_resized.crop((0, crop_y, target_w, crop_y + seg_h))
                    part.save(target_path, "PNG")
                    crop_y += seg_h
                    prepared.append(SliceItem(
                        path=str(target_path),
                        href=s.href,
                        alt_text=s.alt_text,
                        sort_key=s.sort_key,
                        original_width=target_w,
                    ))
        except Exception:
            for s in seg_list:
                prepared.append(s)

    # 2. 处理 hotspot 行：同一源图先完整重组，只做一次 LANCZOS 缩放，再切回。
    # 独立缩放每一行会在行边界重复采样，Outlook 中容易表现为细线或错位。
    #
    # V6.4.0 结构性根修（单行列网格）：把网格转置成"列"结构。
    # 旧实现按行输出 PNG，HTML 侧随之生成"每行一条 <tr>"；Outlook Word 引擎在
    # <tr> 之间始终插入约 1px 间距（见模块 docstring V4.9.0），一封 3 按钮邮件
    # 实测 9 条 <tr> → 8 处缝隙。新实现取所有行 X 边界的并集作为列，
    # 每列输出一张竖向长条 PNG（grid_col/grid_row 标记坐标），
    # HTML 侧只需 1 条 <tr>：每列 1 个 <td>，列内 display:block 连续堆叠 ——
    # 与普通长图已验证无缝的结构完全一致。
    hotspot_sources: Dict[int, List[Tuple[Tuple[int, int], List[SliceItem]]]] = {}
    for key in sorted(hotspot_rows_map):
        hotspot_sources.setdefault(key[0], []).append((key, hotspot_rows_map[key]))

    for _src_idx, keyed_groups in sorted(hotspot_sources.items()):
        fallback_groups = [group for _, group in keyed_groups]
        try:
            row_records = []
            source_width = 0
            source_height = 0
            for _key, group in keyed_groups:
                if not group:
                    continue
                source_parts = []
                row_width = 0
                row_height = 0
                for s in sorted(group, key=lambda item: item.sort_key):
                    with Image.open(s.path) as img:
                        part = img.convert("RGB").copy()
                    source_parts.append((s, part))
                    row_width += part.width
                    row_height = max(row_height, part.height)
                if row_width <= 0 or row_height <= 0:
                    raise ValueError("invalid hotspot row size")

                row_image = Image.new("RGB", (row_width, row_height))
                x = 0
                for _, part in source_parts:
                    row_image.paste(part, (x, 0))
                    x += part.width
                allocated = _allocate_group_widths(group, display_w_even)
                row_records.append((source_parts, row_image, allocated))
                source_width = max(source_width, row_width)
                source_height += row_height

            if not row_records or source_width <= 0 or source_height <= 0:
                raise ValueError("invalid hotspot source size")

            if any(row_image.width != source_width for _, row_image, _ in row_records):
                raise ValueError("hotspot rows do not share one source width")

            target_height = _even_pixel_4x(
                max(1, round(source_height * display_w_even / source_width))
            )
            output_heights = _allocate_axis_4x(
                [row_image.height for _, row_image, _ in row_records],
                target_height,
            )

            full_source = Image.new("RGB", (source_width, source_height))
            source_y = 0
            for _parts, row_image, _allocated in row_records:
                full_source.paste(row_image, (0, source_y))
                source_y += row_image.height

            full_resized = full_source.resize(
                (display_w_even, target_height), Image.LANCZOS
            )

            # V6.4.0：先算出每行在显示空间的 X 区间，再取所有行边界的并集作为列。
            # 同一行的分段只属于该行；一个全局列可能落在某行某个分段内部，
            # 此时该列的图就是那个分段的一次裁剪（<a> 归属跟随所属分段）。
            row_spans: List[List[Tuple[int, int, SliceItem]]] = []
            for source_parts, _row_image, allocated in row_records:
                spans: List[Tuple[int, int, SliceItem]] = []
                cursor = 0
                for s, _part in source_parts:
                    width = int(allocated.get(s.path, display_w_even))
                    spans.append((cursor, cursor + width, s))
                    cursor += width
                if cursor != display_w_even:
                    raise ValueError("hotspot row width contract failed")
                row_spans.append(spans)

            column_edges = sorted({0, display_w_even} | {
                edge
                for spans in row_spans
                for left, right, _s in spans
                for edge in (left, right)
            })

            crop_y = 0
            for row_index, output_height in enumerate(output_heights):
                spans = row_spans[row_index]
                sub_index_by_owner: Dict[int, int] = {}
                for col_index in range(len(column_edges) - 1):
                    left = column_edges[col_index]
                    right = column_edges[col_index + 1]
                    owner = next(
                        (s for span_left, span_right, s in spans
                         if span_left <= left and right <= span_right),
                        None,
                    )
                    if owner is None:
                        raise ValueError(
                            "hotspot column "
                            f"{left}-{right} has no owning segment in row {row_index}"
                        )
                    sub_index = sub_index_by_owner.get(id(owner), 0)
                    sub_index_by_owner[id(owner)] = sub_index + 1
                    counter += 1
                    target_path = out_dir / f"mail_{batch}_{counter:03d}.png"
                    full_resized.crop(
                        (left, crop_y, right, crop_y + output_height)
                    ).save(target_path, "PNG")
                    # sort_key 追加 1e-10 级亚序，保证同一 owner 的多个列裁片
                    # 在稳定排序下自左向右；不影响千分位 row / 百万分位 col 解码。
                    prepared.append(SliceItem(
                        path=str(target_path), href=owner.href, alt_text=owner.alt_text,
                        sort_key=owner.sort_key + sub_index * 1e-10,
                        original_width=display_w_even,
                        grid_col=col_index, grid_row=row_index,
                    ))
                crop_y += output_height
            if crop_y != target_height:
                raise ValueError("hotspot column grid height contract failed")
        except Exception:
            for group in fallback_groups:
                prepared.extend(group)

    # 按 sort_key 排序返回
    prepared.sort(key=lambda s: s.sort_key)
    return prepared


def materialize_display_slices_strict(slices: List[SliceItem], display_w: int = 650) -> List[SliceItem]:
    """
    生成最终显示尺寸切片，并拒绝 materialize_display_slices 的静默降级结果。

    Outlook 发送路径依赖实际 PNG 尺寸与 HTML width/height 完全一致。若预渲染失败后
    返回原图，Word 引擎会重新缩放图片，容易重新出现 1px 缝隙。

    V4.8.7：登记所有新建临时文件，调用方可用 cleanup_temp_slices 删除。
    """
    if not slices:
        return []

    original_paths = {s.path for s in slices}
    prepared = materialize_display_slices(slices, display_w)
    prepared_paths = [s.path for s in prepared]
    fallback_paths = [p for p in prepared_paths if p in original_paths]
    missing_paths = [p for p in prepared_paths if not Path(p).exists()]

    # V6.4.0: 热点链路会把切片细分成"列 × 行"网格单元，数量可能多于输入，
    # 因此数量校验放宽为"网格化输出不少于输入"；静默降级（返回原文件）仍被拒绝。
    grid_expanded = (
        bool(prepared)
        and all(s.grid_col >= 0 and s.grid_row >= 0 for s in prepared)
        and len(prepared) >= len(slices)
    )
    if fallback_paths or missing_paths or (
        len(prepared) != len(slices) and not grid_expanded
    ):
        raise RuntimeError(
            "最终邮件切片预渲染失败，已阻止发送以避免 Outlook 中出现图片缝隙。"
            "请重新切图后再试。"
        )

    # V4.8.7: 跟踪新建的临时文件，便于调用方清理
    new_files = [p for p in prepared_paths if p not in original_paths]
    _track_temp_files(new_files)

    return prepared


def assemble_html(slices: List[SliceItem], display_w: int = 650,
                  prepared: bool = False) -> str:
    """
    生成适用于 Outlook 的 HTML 邮件正文（CID 内联嵌入版）。

    V4.6.9 重构：同 source_index 的多段拼成 1 个 <tr>（横向拼接），
    不同 source_index 之间用独立 <tr>（纵向堆叠）。这样:
      1. 单张原图的所有段（包括 hotspot 派生竖条）拼成 1 行 → 恢反原图视觉
      2. 多张原图（智能切图切了 N 段 Y）→ N 行 × K 列

    V4.7.8: 最后清理图片尺寸缓存
    V4.9.3: 普通链路使用图片实际宽度，不归一化到 4 的倍数
    V6.4.0: 热点链路改为单行列网格 —— 整封邮件只有 1 条 <tr>、无嵌套表格，
            每列 1 个 <td>，列内 display:block 连续堆叠（与普通长图同一套写法），
            从结构上根除 Outlook Word 引擎在 <tr> 之间插入的 1px 缝隙。
    """
    try:
        sorted_slices = sorted(slices, key=lambda s: s.sort_key)
        groups = _group_by_source(sorted_slices)
        layout_attr = ""
        if _is_plain_vertical_stack(groups) and not _is_single_row_grid(slices):
            # V4.9.3: 普通链路使用图片实际宽度，不归一化到 4 的倍数。
            # V3.0 无缝版本直接用原始宽度，避免 650→652 拉伸导致缝隙。
            try:
                actual_w, _ = _get_img_dimensions(groups[0][0].path)
                effective_w = actual_w if actual_w > 0 else _normalize_display_width(display_w)
            except Exception:
                effective_w = _normalize_display_width(display_w)
            content_blocks, cid_counter = _build_v3_plain_image_stack(
                groups, effective_w, is_base64=False
            )
            row_cells = (
                f'<td align="left" valign="top" width="{effective_w}" style="'
                f'width: {effective_w}px; padding: 0; margin: 0; border: 0; '
                f'border-collapse: collapse; border-spacing: 0; '
                f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
                f'vertical-align: top; '
                f'mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px; '
                f'mso-text-raise: 0;">\n'
                f'{content_blocks}'
                f'</td>\n'
            )
        else:
            effective_w = _normalize_display_width(display_w)
            # Fix 1-B: 非普通链路（hotspot/多段）先 materialize，保证 PNG 物理尺寸
            # 与 HTML 声明的 4x 宽/高严格一致，消除纵向/横向错位与表间缝隙。
            # V6.4.0: materialize 现在直接产出单行列网格单元；已经是网格单元的
            # 切片不再重复 materialize（否则会二次切分、宽度对不上）。
            # 临时文件由 materialize_display_slices_strict 内部 _track_temp_files 登记，
            # 调用方可用 cleanup_temp_slices 清理（V5 main.py 已做）。
            if not _is_single_row_grid(slices):
                slices = materialize_display_slices_strict(slices, effective_w)
            cid_by_sort_key = {
                item.sort_key: f"slice_{index:03d}"
                for index, item in enumerate(_ordered_grid_cells(slices), start=1)
            }
            row_cells = _build_single_row_column_grid(
                slices, effective_w, is_base64=False,
                cid_by_sort_key=cid_by_sort_key,
            )
            layout_attr = ' data-layout="hotspot-grid"'

        # 普通链路：V3 连续 img；hotspot/多段链路：分组表格。
        return (
            f'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
            f'"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office" '
            f'xmlns:v="urn:schemas-microsoft-com:vml">\n'
            f'<head>\n'
            f'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f'<!--[if gte mso 9]><xml><o:OfficeDocumentSettings><o:AllowPNG/>'
            f'<o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml><![endif]-->\n'
            f'<title>长图邮件</title>\n'
            f'</head>\n'
            f'<body style="margin: 0; padding: 0; background-color: #ffffff; '
            f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
            f'Margin: 0;">\n'
            f'<table role="presentation"{layout_attr} cellpadding="0" cellspacing="0" border="0" '
            f'align="center" '
            f'width="{effective_w}" '
            f'style="width: {effective_w}px; border: 0; border-collapse: collapse; border-spacing: 0; '
            f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
            f'mso-table-lspace: 0pt; mso-table-rspace: 0pt; '
            f'mso-table-bspace: 0pt; mso-table-tspace: 0pt; '
            f'mso-table-bspace-snap: 1000; mso-table-tspace-snap: 1000; '
            f'table-layout: fixed;">\n'
            f'<tr valign="top" align="left" style="'
            f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
            f'mso-margin-top-alt: 0; mso-margin-bottom-alt: 0;">\n'
            f'{row_cells}'
            f'</tr>\n'
            f'</table>\n'
            f'</body>\n'
            f'</html>'
        )
    finally:
        # V4.7.8: 清理缓存，释放内存
        _clear_dimensions_cache()


def get_cid_map(slices: List[SliceItem]) -> Dict[int, str]:
    """返回 {index: cid} 映射，给 outlook_sender.py 用。"""
    sorted_slices = sorted(slices, key=lambda s: s.sort_key)
    return {i: f"slice_{i + 1:03d}" for i in range(len(sorted_slices))}


def generate_plain_html(slices: List[SliceItem], display_w: int = 650) -> str:
    """
    生成纯内联 base64 的 HTML，供复制到剪贴板使用（不进 Outlook，直接贴到 Gmail / 网页邮箱）。

    V4.6.9 重构：同 assemble_html 一样按 source_index 分组横向拼接。
    V4.7.8: 最后清理图片尺寸缓存。
    V4.8.1: 入口先 materialize_display_slices，
    保证实际 PNG 高度与 HTML 声明 height 严格一致，
    避免 1px 溢出导致的 Outlook 纵向缝（根因 H3：generate_plain_html
    独立调用时跳过 materialize，row_height 偶数化后的高度与实际 PNG 不一致）。
    V4.8.1.1: materialize 内部静默降级会导致本修复失效，入口加 guard
    确保 materialize 实际产生了新文件（路径以 mail_ 开头）。
    V4.9.3: 普通链路跳过 materialize，使用图片实际宽度，与 assemble_html 保持一致。
    V6.4.0: 热点链路与 assemble_html 一样改为单行列网格（1 条 <tr>，无嵌套表格）。
    """
    try:
        sorted_slices = sorted(slices, key=lambda s: s.sort_key)
        groups = _group_by_source(sorted_slices)
        layout_attr = ""
        if _is_plain_vertical_stack(groups) and not _is_single_row_grid(slices):
            # V4.9.3: 普通链路跳过 materialize，使用图片实际宽度。
            # V3.0 无缝版本不经过 materialize，直接用原始切片。
            try:
                actual_w, _ = _get_img_dimensions(groups[0][0].path)
                effective_w = actual_w if actual_w > 0 else _normalize_display_width(display_w)
            except Exception:
                effective_w = _normalize_display_width(display_w)
            content_blocks, cid_counter = _build_v3_plain_image_stack(
                groups, effective_w, is_base64=True
            )
            row_cells = (
                f'<td align="left" valign="top" width="{effective_w}" style="'
                f'width: {effective_w}px; padding: 0; margin: 0; border: 0; '
                f'border-collapse: collapse; border-spacing: 0; '
                f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
                f'vertical-align: top; '
                f'mso-padding-alt: 0; mso-border-alt: solid #FFFFFF 0px; '
                f'mso-text-raise: 0;">\n'
                f'{content_blocks}'
                f'</td>\n'
            )
        else:
            # hotspot/复杂链路：保留 materialize 预渲染
            effective_w = _normalize_display_width(display_w)
            if not _is_single_row_grid(slices):
                slices = materialize_display_slices_strict(slices, effective_w)
            row_cells = _build_single_row_column_grid(
                slices, effective_w, is_base64=True
            )
            layout_attr = ' data-layout="hotspot-grid"'
        return (
            f'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
            f'"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml">\n'
            f'<head>\n'
            f'<meta http-equiv="Content-Type" content="text/html; charset=utf-8">\n'
            f'<title>长图邮件</title>\n'
            f'</head>\n'
            f'<body style="margin: 0; padding: 0; background-color: #ffffff; '
            f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
            f'Margin: 0;">\n'
            f'<div align="center" style="width: 100%; text-align: center; margin: 0; padding: 0;">\n'
            f'<table role="presentation"{layout_attr} cellpadding="0" cellspacing="0" border="0" '
            f'align="center" '
            f'width="{effective_w}" '
            f'style="width: {effective_w}px; border: 0; border-collapse: collapse; border-spacing: 0; '
            f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
            f'mso-table-lspace: 0pt; mso-table-rspace: 0pt; '
            f'mso-table-bspace: 0pt; mso-table-tspace: 0pt; '
            f'mso-table-bspace-snap: 1000; mso-table-tspace-snap: 1000; '
            f'table-layout: fixed;">\n'
            f'<tr valign="top" align="left" style="'
            f'font-size: 0; line-height: 0; mso-line-height-rule: exactly; '
            f'mso-margin-top-alt: 0; mso-margin-bottom-alt: 0;">\n'
            f'{row_cells}'
            f'</tr>\n'
            f'</table>\n'
            f'</div>\n'
            f'</body>\n'
            f'</html>'
        )
    finally:
        # V4.7.8: 清理缓存，释放内存
        _clear_dimensions_cache()
