"""Pytest path setup for the desktop PySide layout."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_UI = ROOT / "desktop"

for path in (DESKTOP_UI,):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
