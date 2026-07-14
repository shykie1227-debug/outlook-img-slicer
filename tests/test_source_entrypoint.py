import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent.parent


def test_documented_desktop_script_starts_from_project_root():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["QT_QPA_PLATFORM"] = "offscreen"
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "desktop" / "main.py")],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(1.5)
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=2)
            raise AssertionError(
                f"desktop/main.py exited during startup ({process.returncode})\n"
                f"stdout: {stdout}\nstderr: {stderr}"
            )
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
