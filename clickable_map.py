"""
可点击热区（hotspot）管理模块

数据模型：
  hotspots: Dict[str, List[Hotspot]]
    key   = 切片文件名（slice_001.png）
    value = 该切片上的热区列表

热区对象：
  x1, y1, x2, y2 : 矩形坐标（基于切片像素，非缩略图）
  text           : 按钮文字（用于显示 + alt）
  url            : 跳转 URL
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import json


@dataclass
class Hotspot:
    x1: int
    y1: int
    x2: int
    y2: int
    text: str
    url: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Hotspot":
        return cls(
            x1=int(d["x1"]), y1=int(d["y1"]),
            x2=int(d["x2"]), y2=int(d["y2"]),
            text=str(d.get("text", "")),
            url=str(d.get("url", "")),
        )

    def normalized(self) -> "Hotspot":
        """保证 (x1,y1) 是左上角、(x2,y2) 是右下角"""
        x1, x2 = sorted((self.x1, self.x2))
        y1, y2 = sorted((self.y1, self.y2))
        return Hotspot(x1=x1, y1=y1, x2=x2, y2=y2, text=self.text, url=self.url)


class HotspotMap:
    """管理所有切片的热区数据，支持序列化/反序列化。"""

    def __init__(self):
        # key = slice 文件名（如 "slice_001.png"），value = List[Hotspot]
        self._map: Dict[str, List[Hotspot]] = {}

    def add(self, slice_filename: str, hotspot: Hotspot):
        self._map.setdefault(slice_filename, []).append(hotspot.normalized())

    def remove(self, slice_filename: str, index: int) -> Optional[Hotspot]:
        if slice_filename not in self._map:
            return None
        lst = self._map[slice_filename]
        if 0 <= index < len(lst):
            return lst.pop(index)
        return None

    def get(self, slice_filename: str) -> List[Hotspot]:
        return list(self._map.get(slice_filename, []))

    def all_slices(self) -> List[str]:
        return list(self._map.keys())

    def is_empty(self) -> bool:
        return not any(self._map.values())

    def total_count(self) -> int:
        return sum(len(v) for v in self._map.values())

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
                m.add(k, Hotspot.from_dict(h))
        return m

    def clear(self):
        self._map.clear()
