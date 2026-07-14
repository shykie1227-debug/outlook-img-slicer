import re
from pathlib import Path

import main


ROOT = Path(__file__).resolve().parent.parent
DESKTOP_ROOT = ROOT / "desktop"


def test_release_version_is_synchronized_for_v6_2_2():
    version_info = (DESKTOP_ROOT / "version_info.txt").read_text(encoding="utf-8")

    assert main.VERSION == "6.2.2"
    assert "6.2.2.20260713" in version_info
    assert "OutlookImgSlicer.exe" in version_info
    assert re.search(r"filevers=\(6,\s*2,\s*2,\s*2026\)", version_info)
