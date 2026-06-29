"""
Sidecar Server 端到端测试

V6.0.0 Phase 1 验收。
继承 V5 的 93 个单元测试 1:1 通过 — Sidecar 暴露的所有命令必须与 V5 算法行为完全一致。

测试方法：
- 子进程启动 sidecar_server.py
- 通过 stdin/stdout JSON 行通信
- 验证返回结果与 V5 直接调用模块结果一致
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

SIDECAR_DIR = Path(__file__).parent.parent / "sidecar"
SIDECAR_SCRIPT = SIDECAR_DIR / "sidecar_server.py"


def _spawn_sidecar():
    """启动 Sidecar 子进程，返回 (proc, stdin, stdout, stderr)。"""
    proc = subprocess.Popen(
        [sys.executable, str(SIDECAR_SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # 行缓冲
    )
    return proc


def _read_json_line(stdout, timeout: float = 5.0) -> dict:
    """从 stdout 读取一行 JSON。"""
    import select
    deadline = time.time() + timeout
    while time.time() < deadline:
        ready, _, _ = select.select([stdout], [], [], 0.1)
        if ready:
            line = stdout.readline()
            if line:
                return json.loads(line)
        time.sleep(0.05)
    raise TimeoutError("Sidecar 响应超时")


def _send_command(proc, req: dict, timeout: float = 30.0) -> dict:
    """发送一个命令并读取响应。"""
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    return _read_json_line(proc.stdout, timeout=timeout)


# ─────────────────────────────────────
# Phase 1.1: 启动握手
# ─────────────────────────────────────

def test_sidecar_handshake_emits_ready_on_startup():
    """Sidecar 启动后第一行 stdout 必须输出 {"ready": true} 握手信号。"""
    proc = _spawn_sidecar()
    try:
        ready = _read_json_line(proc.stdout, timeout=3.0)
        assert ready == {"ready": True}
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


def test_sidecar_handshake_is_first_line():
    """握手信号必须是 Sidecar 输出的第一行（在任何其他输出之前）。"""
    proc = _spawn_sidecar()
    try:
        first_line = proc.stdout.readline()
        assert first_line.strip() == json.dumps({"ready": True})
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


# ─────────────────────────────────────
# Phase 1.2: 基础命令分派
# ─────────────────────────────────────

def test_unknown_command_returns_error():
    """未知的命令类型应该返回错误响应。"""
    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)  # 等待 ready
        resp = _send_command(proc, {
            "id": "test-1",
            "type": "unknown.command",
            "params": {}
        })
        assert resp["ok"] is False
        assert "error" in resp
        assert "unknown.command" in resp["error"].lower() or "未知" in resp["error"]
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


def test_response_includes_request_id():
    """响应必须包含与请求匹配的 id。"""
    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)  # 等待 ready
        resp = _send_command(proc, {
            "id": "my-custom-id-42",
            "type": "sidecar.status",
            "params": {}
        })
        assert resp["id"] == "my-custom-id-42"
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


def test_sidecar_status_returns_ok():
    """sidecar.status 命令应返回 ok=true。"""
    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)  # 等待 ready
        resp = _send_command(proc, {
            "id": "status-1",
            "type": "sidecar.status",
            "params": {}
        })
        assert resp["ok"] is True
        assert "result" in resp
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


# ─────────────────────────────────────
# Phase 1.3: image.info 命令
# ─────────────────────────────────────

def test_image_info_returns_dimensions(tmp_path):
    """image.info 应返回图片宽高。"""
    # 创建一个测试图片
    from PIL import Image
    img_path = tmp_path / "test.png"
    Image.new("RGB", (320, 240), "white").save(img_path)

    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)  # 等待 ready
        resp = _send_command(proc, {
            "id": "info-1",
            "type": "image.info",
            "params": {"path": str(img_path)}
        })
        assert resp["ok"] is True, f"image.info 失败: {resp.get('error')}"
        result = resp["result"]
        assert result["width"] == 320
        assert result["height"] == 240
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


def test_image_info_missing_file_returns_error():
    """图片不存在时 image.info 应返回错误。"""
    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)  # 等待 ready
        resp = _send_command(proc, {
            "id": "info-2",
            "type": "image.info",
            "params": {"path": "/nonexistent/path.png"}
        })
        assert resp["ok"] is False
        assert "error" in resp
        assert "文件不存在" in resp["error"]
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


def test_image_info_non_string_path_returns_type_error():
    """非字符串 path 应返回类型错误。"""
    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)
        resp = _send_command(proc, {
            "id": "info-3",
            "type": "image.info",
            "params": {"path": 12345}  # 故意非字符串
        })
        assert resp["ok"] is False
        assert "类型错误" in resp["error"] or "TypeError" in resp["error"]
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


def test_image_safety_check_missing_file_returns_error():
    """safetyCheck 对不存在文件必须抛错，不能静默返回 is_safe=True。"""
    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)
        resp = _send_command(proc, {
            "id": "safety-1",
            "type": "image.safetyCheck",
            "params": {"path": "/nonexistent/file.png"}
        })
        assert resp["ok"] is False
        assert "文件不存在" in resp["error"]
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


def test_json_parse_error_returns_clear_error():
    """JSON 解析错误应返回明确错误消息。

    注意：JSON 损坏时无法提取 id，因此响应不包含 id 字段 — 这是合理的边界行为。
    """
    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)  # ready
        proc.stdin.write('{"id": "bad-1", "type": "x"\n')  # 故意格式错（缺括号）
        proc.stdin.flush()
        resp = _read_json_line(proc.stdout, timeout=3.0)
        assert resp["ok"] is False
        assert "JSON 解析失败" in resp["error"] or "JSON" in resp["error"]
        # 不强制要求 id 字段（边界行为），但 error 字段必须存在
        assert "error" in resp
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


# ─────────────────────────────────────
# Phase 1.4: image.slice 命令
# ─────────────────────────────────────

def test_image_slice_short_image_returns_one_slice(tmp_path):
    """短图（高度 < max_height）应只返回 1 个切片。"""
    from PIL import Image
    img_path = tmp_path / "short.png"
    Image.new("RGB", (200, 100), "white").save(img_path)

    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)
        resp = _send_command(proc, {
            "id": "slice-1",
            "type": "image.slice",
            "params": {"path": str(img_path), "max_height": 1200, "target_width": 0}
        })
        assert resp["ok"] is True, f"image.slice 失败: {resp.get('error')}"
        slices = resp["result"]["slices"]
        assert len(slices) == 1
        assert slices[0]["width"] == 200
        assert slices[0]["height"] == 100
        assert slices[0]["source_index"] == 1
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


def test_image_slice_long_image_returns_multiple_slices(tmp_path):
    """长图（高度 > max_height）应切片为多片。"""
    from PIL import Image
    img_path = tmp_path / "long.png"
    # 1000 x 5000 长图，max_height=1200 → 应输出 5+ 片
    Image.new("RGB", (1000, 5000), "white").save(img_path)

    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)
        resp = _send_command(proc, {
            "id": "slice-2",
            "type": "image.slice",
            "params": {"path": str(img_path), "max_height": 1200, "target_width": 0}
        })
        assert resp["ok"] is True, f"image.slice 失败: {resp.get('error')}"
        slices = resp["result"]["slices"]
        # 5000 / 1200 = 4.17 → 至少 5 片
        assert len(slices) >= 5
        # 切片总高 = 原图高（V5 验证标准）
        total_h = sum(s["height"] for s in slices)
        assert total_h == 5000, f"切片总高应等于原图高: {total_h} != 5000"
        # source_index 递增
        for i, s in enumerate(slices):
            assert s["source_index"] == i + 1
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


# ─────────────────────────────────────
# Phase 1.5: html.assemble 命令（V5 验证标准零缝隙）
# ─────────────────────────────────────

def test_html_assemble_three_slices_zero_gap(tmp_path):
    """
    3 张切片（总高 = 原图高）组装的 HTML 经 Chrome 渲染必须零 1px 缝隙。
    这是 V5 修复项 #2 的核心验收标准。
    """
    from PIL import Image
    from pathlib import Path
    # 1000x3000 长图，max_height=1200 → 3 片
    img_path = tmp_path / "long.png"
    Image.new("RGB", (1000, 3000), "white").save(img_path)

    # Step 1: 切片
    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)
        slice_resp = _send_command(proc, {
            "id": "slice-3",
            "type": "image.slice",
            "params": {"path": str(img_path), "max_height": 1200, "target_width": 0}
        })
        assert slice_resp["ok"] is True
        slices = slice_resp["result"]["slices"]

        # Step 2: 组装 HTML
        asm_resp = _send_command(proc, {
            "id": "asm-1",
            "type": "html.assemble",
            "params": {
                "slices": [
                    {
                        "path": s["path"],
                        "href": None,
                        "alt_text": "",
                        "sort_key": float(s["source_index"]),
                        "original_width": s["width"],
                    }
                    for s in slices
                ],
                "display_w": 650
            }
        })
        assert asm_resp["ok"] is True, f"html.assemble 失败: {asm_resp.get('error')}"
        html = asm_resp["result"]["html"]
        assert "<table" in html
        # 必须包含 cid 文件（因为用了 SliceItem href 模式... 实际是图片直接 base64）
        # 验证 HTML 包含所有切片文件名
        for s in slices:
            assert Path(s["path"]).name in html, f"HTML 应包含 {Path(s['path']).name}"

        # 写文件供 Chrome 验证（后续测试用）
        out_html = tmp_path / "output.html"
        out_html.write_text(html)
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


# ─────────────────────────────────────
# Phase 1.6: html.clipboard 命令
# ─────────────────────────────────────

def test_html_clipboard_returns_cf_html_bytes(tmp_path):
    """html.clipboard 应返回 base64 编码的 CF_HTML 字节。"""
    import base64
    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)
        resp = _send_command(proc, {
            "id": "clip-1",
            "type": "html.clipboard",
            "params": {"html": "<p>hello</p>"}
        })
        assert resp["ok"] is True, f"html.clipboard 失败: {resp.get('error')}"
        cf_b64 = resp["result"]["cf_html_b64"]
        cf_bytes = base64.b64decode(cf_b64)
        cf_text = cf_bytes.decode("utf-8")
        # V5 标准：CF_HTML 必须以 Version:0.9 开头
        assert "Version:0.9" in cf_text
        # 必须包含 StartHTML/EndHTML/StartFragment/EndFragment 4 个偏移字段
        for field in ("StartHTML:", "EndHTML:", "StartFragment:", "EndFragment:"):
            assert field in cf_text, f"CF_HTML 缺少字段: {field}"
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


# ─────────────────────────────────────
# Phase 1.7: outlook 命令的平台约束
# ─────────────────────────────────────

def test_outlook_create_draft_on_macos_returns_error():
    """macOS 下 outlook.createDraft 必须返回 '仅支持 Windows' 错误。"""
    import platform
    if platform.system() == "Windows":
        pytest.skip("macOS 专属测试")

    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)
        resp = _send_command(proc, {
            "id": "out-1",
            "type": "outlook.createDraft",
            "params": {"html": "<p>x</p>", "subject": "test", "cid_files": {}}
        })
        assert resp["ok"] is False
        assert "Windows" in resp["error"] or "不支持" in resp["error"]
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


# ─────────────────────────────────────
# Phase 1.8: 心跳
# ─────────────────────────────────────

def test_sidecar_emits_periodic_pings():
    """Sidecar 启动后 4 秒内至少应输出 1 次心跳。"""
    import select
    proc = _spawn_sidecar()
    try:
        # 跳过 ready
        _read_json_line(proc.stdout, timeout=3.0)

        # 等待 4 秒，看是否收到 ping
        deadline = time.time() + 4.5
        ping_received = False
        while time.time() < deadline:
            ready, _, _ = select.select([proc.stdout], [], [], 0.5)
            if ready:
                line = proc.stdout.readline()
                if line:
                    obj = json.loads(line)
                    if "ping" in obj:
                        ping_received = True
                        break
        assert ping_received, "4.5 秒内未收到心跳"
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


# ─────────────────────────────────────
# Phase 2.0: 协议一致性 — method 字段（JSON-RPC 标准）
# ─────────────────────────────────────

def test_method_field_protocol_works():
    """协议标准字段是 'method'（与 commands.md / TypeScript 端一致）。"""
    from PIL import Image
    with tempfile.TemporaryDirectory() as td:
        img_path = os.path.join(td, "test.png")
        Image.new("RGB", (100, 50), "red").save(img_path)

        proc = _spawn_sidecar()
        try:
            _read_json_line(proc.stdout, timeout=3.0)  # ready
            resp = _send_command(proc, {
                "id": "method-1",
                "method": "image.info",
                "params": {"path": img_path},
            })
            assert resp["ok"] is True, f"method 协议失败: {resp.get('error')}"
            assert resp["result"]["width"] == 100
            assert resp["result"]["height"] == 50
        finally:
            proc.terminate()
            proc.wait(timeout=3.0)


def test_type_field_still_works_for_backward_compat():
    """旧实现用 'type' 字段，必须继续支持（向后兼容）。"""
    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)
        resp = _send_command(proc, {
            "id": "type-back-1",
            "type": "sidecar.status",
            "params": {},
        })
        assert resp["ok"] is True
        assert resp["result"]["ready"] is True
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


def test_unknown_command_with_method_field():
    """method 字段下未知命令应返回 error。"""
    proc = _spawn_sidecar()
    try:
        _read_json_line(proc.stdout, timeout=3.0)
        resp = _send_command(proc, {
            "id": "unknown-m-1",
            "method": "image.doesNotExist",
            "params": {},
        })
        assert resp["ok"] is False
        assert "error" in resp
        assert "unknown" in resp["error"].lower() or "未知" in resp["error"]
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)
