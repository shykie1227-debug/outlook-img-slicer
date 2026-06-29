import re
from pathlib import Path

import main


ROOT = Path(__file__).resolve().parent.parent


def test_release_version_is_synchronized_for_v5():
    version_info = (ROOT / "version_info.txt").read_text(encoding="utf-8")

    assert main.VERSION == "5.0.0"
    assert "5.0.0.20260629" in version_info
    assert re.search(r"filevers=\(5,\s*0,\s*0,\s*20260629\)", version_info)
