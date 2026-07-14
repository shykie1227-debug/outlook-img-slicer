"""
可点击热区（hotspot）管理模块

数据模型：
  hotspots: Dict[str, List[Hotspot]]
    key   = 切片文件名（slice_001.png）
    value = 该切片上的热区列表

热区对象：
  x1, y1, x2, y2 : 矩形坐标（基于切片像素，非缩略图）
  url            : 跳转 URL（必填）
  text           : 按钮文字（可选，V4.6.1 起默认空，仅用于 alt 兜底）
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
import json
from urllib.parse import urlparse


@dataclass
class Hotspot:
    x1: int
    y1: int
    x2: int
    y2: int
    url: str
    text: str = ""  # 可选：仅用于 alt 兜底文字，不出现在图上
    # ── V4.6.7 排序架构 ──
    source_index: float = 0.0  # 标注时所属原切片的 source_index（int=1.0, 2.0, ...）

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Hotspot":
        return cls(
            x1=int(d["x1"]), y1=int(d["y1"]),
            x2=int(d["x2"]), y2=int(d["y2"]),
            url=str(d.get("url", "")),
            text=str(d.get("text", "")),
            source_index=float(d.get("source_index", 0.0)),
        )

    def normalized(self) -> "Hotspot":
        """保证 (x1,y1) 是左上角、(x2,y2) 是右下角。V4.6.7 修复：透传 source_index。"""
        x1, x2 = sorted((self.x1, self.x2))
        y1, y2 = sorted((self.y1, self.y2))
        return Hotspot(
            x1=x1, y1=y1, x2=x2, y2=y2,
            url=self.url, text=self.text,
            source_index=self.source_index,
        )

    def rect(self) -> Tuple[int, int, int, int]:
        """返回 (x1, y1, x2, y2) 标准化后的元组。"""
        n = self.normalized()
        return (n.x1, n.y1, n.x2, n.y2)


# ── 错误码：让 UI 层可以无文案依赖地区分错误类型 ──
class HotspotError:
    EMPTY_URL = "URL 不能为空"
    TOO_SMALL = "选区太小（需 ≥ 5×5px），请重新拖选"
    DUPLICATE = "该区域已存在，请勿重复添加"
    OUT_OF_RANGE = "热区索引越界"
    NO_HOTSPOTS = "该切片未添加任何热区"
    INVALID_URL = "链接仅支持 http:// 或 https:// 地址"
    OVERLAP = "热区与已有按钮区域重叠，请移动或缩小选区"


def _normalize_web_url(url: str) -> Tuple[Optional[str], str]:
    value = (url or "").strip()
    if not value:
        return None, HotspotError.EMPTY_URL
    parsed = urlparse(value)
    if not parsed.scheme:
        value = "https://" + value
        parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None, HotspotError.INVALID_URL
    return value, ""


def _rectangles_overlap(a: Hotspot, b: Hotspot, tolerance: int = 3) -> bool:
    x_overlap = min(a.x2, b.x2) - max(a.x1, b.x1)
    y_overlap = min(a.y2, b.y2) - max(a.y1, b.y1)
    return x_overlap > tolerance and y_overlap > 0


class HotspotMap:
    """管理所有切片的热区数据，支持序列化/反序列化。"""

    def __init__(self):
        # key = slice 文件名（如 "slice_001.png"），value = List[Hotspot]
        self._map: Dict[str, List[Hotspot]] = {}

    def add(self, slice_filename: str, hotspot: Hotspot, source_index: float = 0.0) -> Tuple[bool, str]:
        """
        添加热区，自动跳过：
        - URL 为空
        - 区域过小（宽/高 < 5px）
        - 与该切片上已有热区完全重叠

        Args:
            slice_filename: 切片文件名
            hotspot: 标注数据
            source_index: 该切片在原始顺序中的位置（V4.6.7 排序架构）

        Returns:
            (True, "")  表示添加成功
            (False, reason) 表示被拦截，reason 为说明文案
        """
        url, error = _normalize_web_url(hotspot.url)
        if error:
            return False, error
        effective_source_index = source_index or hotspot.source_index
        h = Hotspot(
            x1=hotspot.x1, y1=hotspot.y1,
            x2=hotspot.x2, y2=hotspot.y2,
            url=url, text=hotspot.text,
            source_index=effective_source_index,
        ).normalized()
        if h.x2 - h.x1 < 5 or h.y2 - h.y1 < 5:
            return False, HotspotError.TOO_SMALL
        for existing in self._map.get(slice_filename, []):
            if (existing.x1, existing.y1, existing.x2, existing.y2) == (h.x1, h.y1, h.x2, h.y2):
                return False, HotspotError.DUPLICATE
            if _rectangles_overlap(existing, h):
                return False, HotspotError.OVERLAP
        self._map.setdefault(slice_filename, []).append(h)
        return True, ""

    def update(self, slice_filename: str, index: int, hotspot: Hotspot) -> Tuple[bool, str]:
        """
        替换指定 index 的热区（用于编辑功能）。
        重复检查会跳过自身。
        V4.6.7 修复：透传 source_index，避免 update 路径丢失排序上下文。
        """
        if slice_filename not in self._map:
            return False, HotspotError.NO_HOTSPOTS
        lst = self._map[slice_filename]
        if not (0 <= index < len(lst)):
            return False, HotspotError.OUT_OF_RANGE
        url, error = _normalize_web_url(hotspot.url)
        if error:
            return False, error
        # V4.6.7：保留原 source_index，若调用方未传则从原 hotspot 取
        source_index = hotspot.source_index or lst[index].source_index
        h = Hotspot(
            x1=hotspot.x1, y1=hotspot.y1,
            x2=hotspot.x2, y2=hotspot.y2,
            url=url, text=hotspot.text,
            source_index=source_index,
        ).normalized()
        if h.x2 - h.x1 < 5 or h.y2 - h.y1 < 5:
            return False, HotspotError.TOO_SMALL
        for i, existing in enumerate(lst):
            if i == index:
                continue
            if (existing.x1, existing.y1, existing.x2, existing.y2) == (h.x1, h.y1, h.x2, h.y2):
                return False, HotspotError.DUPLICATE
            if _rectangles_overlap(existing, h):
                return False, HotspotError.OVERLAP
        lst[index] = h
        return True, ""

    def remove(self, slice_filename: str, index: int) -> Optional[Hotspot]:
        if slice_filename not in self._map:
            return None
        lst = self._map[slice_filename]
        if 0 <= index < len(lst):
            return lst.pop(index)
        return None

    def get(self, slice_filename: str) -> List[Hotspot]:
        return list(self._map.get(slice_filename, []))

    def clone(self) -> "HotspotMap":
        """Return a validated deep copy suitable for transactional editing."""
        return self.from_json(self.to_json())

    def replace_slice(self, slice_filename: str, hotspots: List[Hotspot]) -> Tuple[bool, str]:
        """Atomically replace one slice after validating every candidate."""
        candidate = self.clone()
        candidate._map.pop(slice_filename, None)
        for hotspot in hotspots:
            ok, reason = candidate.add(
                slice_filename, hotspot, source_index=hotspot.source_index
            )
            if not ok:
                return False, reason
        self._map = candidate._map
        return True, ""

    def all_slices(self) -> List[str]:
        return list(self._map.keys())

    def is_empty(self) -> bool:
        return not any(self._map.values())

    def total_count(self) -> int:
        return sum(len(v) for v in self._map.values())

    def validate_for_images(self, image_paths: List[str]) -> Tuple[bool, str]:
        """Read-only send preflight for URLs, bounds and rectangle overlap."""
        from pathlib import Path
        from PIL import Image

        known = {Path(path).name: path for path in image_paths}
        for filename, hotspots in self._map.items():
            if not hotspots:
                continue
            path = known.get(filename)
            if not path:
                return False, f"热区对应的切片不存在：{filename}"
            try:
                with Image.open(path) as image:
                    width, height = image.size
            except Exception as exc:
                return False, f"无法读取热区切片 {filename}：{exc}"

            for index, hotspot in enumerate(hotspots, start=1):
                _, error = _normalize_web_url(hotspot.url)
                if error:
                    return False, f"{filename} 的热区 #{index}：{error}"
                normalized = hotspot.normalized()
                if (normalized.x1 < 0 or normalized.y1 < 0 or
                        normalized.x2 > width or normalized.y2 > height):
                    return False, f"{filename} 的热区 #{index} 坐标越界"
                if normalized.x2 - normalized.x1 < 5 or normalized.y2 - normalized.y1 < 5:
                    return False, f"{filename} 的热区 #{index} 选区太小"

            for left in range(len(hotspots)):
                for right in range(left + 1, len(hotspots)):
                    if _rectangles_overlap(hotspots[left].normalized(), hotspots[right].normalized()):
                        return False, f"{filename} 的热区 #{left + 1} 与 #{right + 1} 重叠"
        return True, ""

    def to_json(self) -> str:
        return json.dumps(
            {k: [h.to_dict() for h in v] for k, v in self._map.items()},
            ensure_ascii=False, indent=2
        )

    @classmethod
    def from_json(cls, s: str) -> "HotspotMap":
        m = cls()
        data = json.loads(s) if s else {}
        for k, hs_list in data.items():
            for h in hs_list:
                # V4.6.7 修复：透传 source_index，避免从 JSON 加载后丢失排序上下文
                hs = Hotspot.from_dict(h)
                ok, _ = m.add(k, hs, source_index=hs.source_index)
                if not ok:
                    # 跳过重复/无效的旧数据，不让一个坏记录炸掉全量加载
                    continue
        return m

    def clear(self):
        self._map.clear()
