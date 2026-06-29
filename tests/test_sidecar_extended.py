"""
Sidecar 扩展命令测试：PDF/PSD/崩溃恢复/跨命令工作流

V6.0.0 Phase 1 扩展验收。
"""
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import pytest

SIDECAR_SCRIPT = Path(__file__).parent.parent / "sidecar" / "sidecar_server.py"


def _spawn():
    return subprocess.Popen(
        [sys.executable, str(SIDECAR_SCRIPT)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )


def _readline(stdout, timeout=5.0):
    import select
    deadline = time.time() + timeout
    while time.time() < deadline:
        r, _, _ = select.select([stdout], [], [], 0.1)
        if r:
            line = stdout.readline()
            if line:
                return json.loads(line)
        time.sleep(0.05)
    raise TimeoutError


def _send(proc, req, timeout=20.0):
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    return _readline(proc.stdout, timeout=timeout)


# ─────────────────────────────────────
# 崩溃恢复测试
# ─────────────────────────────────────

def test_sidecar_survives_long_running_workflow(tmp_path):
    """Sidecar 连续处理 50 个命令不应崩溃。"""
    from PIL import Image
    img_path = tmp_path / "test.png"
    Image.new("RGB", (200, 200), "white").save(img_path)

    proc = _spawn()
    try:
        _readline(proc.stdout, timeout=3.0)  # ready

        # 连续 50 个混合命令
        for i in range(50):
            cmd = i % 3
            if cmd == 0:
                resp = _send(proc, {"id": f"info-{i}", "type": "image.info", "params": {"path": str(img_path)}})
            elif cmd == 1:
                resp = _send(proc, {"id": f"status-{i}", "type": "sidecar.status", "params": {}})
            else:
                resp = _send(proc, {"id": f"safety-{i}", "type": "image.safetyCheck", "params": {"path": str(img_path)}})
            assert resp["ok"] is True, f"第 {i} 个命令失败: {resp.get('error')}"
            assert resp["id"] == {"info": f"info-{i}", "status": f"status-{i}", "safety": f"safety-{i}"}[
                ["info", "status", "safety"][cmd]
            ], f"第 {i} 个命令 id 不匹配"
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


def test_sidecar_graceful_shutdown_on_eof():
    """关闭 stdin 后 Sidecar 应优雅退出（exit code 0）。"""
    proc = _spawn()
    _readline(proc.stdout, timeout=3.0)  # ready
    proc.stdin.close()
    # 等最多 3 秒
    exit_code = proc.wait(timeout=3.0)
    assert exit_code == 0, f"Sidecar 退出码 {exit_code}，期望 0"


# ─────────────────────────────────────
# PDF / PSD 命令（V5 解析能力继承）
# ─────────────────────────────────────

def test_pdf_to_images_real_pdf(tmp_path):
    """真实 PDF 应正确拆页。"""
    import fitz  # PyMuPDF
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    # 创建 2 页 PDF
    for i in range(2):
        page = doc.new_page(width=595, height=842)
        page.insert_text((100, 100), f"Page {i+1}")
    doc.save(str(pdf_path))
    doc.close()

    proc = _spawn()
    try:
        _readline(proc.stdout, timeout=3.0)
        resp = _send(proc, {
            "id": "pdf-1",
            "type": "pdf.toImages",
            "params": {"path": str(pdf_path), "dpi": 72}
        })
        assert resp["ok"] is True, f"pdf.toImages 失败: {resp.get('error')}"
        pages = resp["result"]["pages"]
        assert len(pages) == 2
        for i, p in enumerate(pages):
            assert Path(p["path"]).exists()
            assert p["source_index"] == i + 1
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


def test_psd_to_image_real_psd(tmp_path):
    """真实 PSD 应正确展平。"""
    from psd_tools import PSDImage

    psd_path = tmp_path / "test.psd"
    # psd-tools 1.x 方式创建新 PSD
    psd = PSDImage.new(mode="RGB", size=(300, 200), color=(255, 0, 0))
    psd.save(psd_path)

    proc = _spawn()
    try:
        _readline(proc.stdout, timeout=3.0)
        resp = _send(proc, {
            "id": "psd-1",
            "type": "psd.toImage",
            "params": {"path": str(psd_path), "dpi": 72}
        })
        assert resp["ok"] is True, f"psd.toImage 失败: {resp.get('error')}"
        pages = resp["result"]["pages"]
        assert len(pages) >= 1
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


# ─────────────────────────────────────
# 跨命令工作流（端到端最小验证）
# ─────────────────────────────────────

def test_full_workflow_image_to_html_to_clipboard(tmp_path):
    """完整工作流：image.info → image.slice → html.assemble → html.clipboard。"""
    from PIL import Image
    img_path = tmp_path / "long.png"
    Image.new("RGB", (600, 2500), (100, 200, 50)).save(img_path)

    proc = _spawn()
    try:
        _readline(proc.stdout, timeout=3.0)

        # 1. info
        r1 = _send(proc, {"id": "1", "type": "image.info", "params": {"path": str(img_path)}})
        assert r1["ok"] is True
        assert r1["result"]["width"] == 600

        # 2. slice
        r2 = _send(proc, {
            "id": "2", "type": "image.slice",
            "params": {"path": str(img_path), "max_height": 1200, "target_width": 0}
        })
        assert r2["ok"] is True
        slices = r2["result"]["slices"]
        assert len(slices) >= 3  # 2500 / 1200

        # 3. assemble
        r3 = _send(proc, {
            "id": "3", "type": "html.assemble",
            "params": {
                "slices": [
                    {"path": s["path"], "href": None, "alt_text": "", "sort_key": float(s["source_index"]), "original_width": s["width"]}
                    for s in slices
                ],
                "display_w": 650,
            }
        })
        assert r3["ok"] is True
        html = r3["result"]["html"]

        # 4. clipboard
        r4 = _send(proc, {"id": "4", "type": "html.clipboard", "params": {"html": html}})
        assert r4["ok"] is True
        import base64
        cf = base64.b64decode(r4["result"]["cf_html_b64"]).decode("utf-8")
        assert "Version:0.9" in cf
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


# ─────────────────────────────────────
# 临时目录清理测试
# ─────────────────────────────────────

def test_pdf_temp_dirs_cleaned_on_shutdown():
    """PDF 拆页创建的临时目录应在 Sidecar 退出时被清理。"""
    import fitz
    import tempfile
    import os
    import glob

    pdf_dir = tempfile.mkdtemp(prefix="sidecar_test_")
    pdf_path = os.path.join(pdf_dir, "x.pdf")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((100, 100), "Hi")
    doc.save(pdf_path)
    doc.close()

    before = set(glob.glob("/tmp/sidecar_pdf_*"))

    proc = _spawn()
    _readline(proc.stdout, timeout=3.0)
    r = _send(proc, {
        "id": "clean-1", "type": "pdf.toImages",
        "params": {"path": pdf_path, "dpi": 72}
    })
    assert r["ok"] is True
    proc.stdin.close()
    proc.wait(timeout=3.0)

    after = set(glob.glob("/tmp/sidecar_pdf_*"))
    new_dirs = after - before
    assert len(new_dirs) == 0, f"残留临时目录: {new_dirs}"
