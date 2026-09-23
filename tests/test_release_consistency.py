import re
from pathlib import Path

import main


ROOT = Path(__file__).resolve().parent.parent
DESKTOP_ROOT = ROOT / "desktop"


def test_release_version_is_synchronized_for_v6_4_0():
    version_info = (DESKTOP_ROOT / "version_info.txt").read_text(encoding="utf-8")

    assert main.VERSION == "6.4.0"
    assert "6.4.0.20260923" in version_info
    assert "OutlookImgSlicer.exe" in version_info
    assert re.search(r"filevers=\(6,\s*4,\s*0,\s*2026\)", version_info)
