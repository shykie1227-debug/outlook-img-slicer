#!/usr/bin/env python3
"""Stable release build entrypoint.

For the Windows EXE that users manually test and use, build the desktop/PySide
application under desktop/.
"""

from __future__ import annotations

import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parent
# Keep this literal path for tests and release audits:
# desktop/build.py
DESKTOP_BUILDER = ROOT / "desktop" / "build.py"


if __name__ == "__main__":
    runpy.run_path(str(DESKTOP_BUILDER), run_name="__main__")
