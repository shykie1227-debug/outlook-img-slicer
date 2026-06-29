"""
Sidecar 4 真实场景端到端测试 — V5 黄金标准

继承 V5.0.2 验证标准：4 个真实长图场景的 HTML 经 Chrome headless 渲染后
**零 1px 白线缝隙**。这是 V5 修复项 #2 的核心验收。

测试方法：
1. 生成 4 个真实长图（1000x5000 / 1000x3000 / 1000x1728 / 800x4000）
2. 通过 Sidecar 切片 + 组装 HTML
3. Chrome headless 渲染 + 像素级缝隙检测
"""
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from PIL import Image

SIDECAR_DIR = Path(__file__).parent.parent / "sidecar"
SIDECAR_SCRIPT = SIDECAR_DIR / "sidecar_server.py"

# 4 真实场景
SCENARIOS = [
    {"name": "long_5000", "w": 1000, "h": 5000, "max_h": 1200, "target_w": 0},
    {"name": "long_3000", "w": 1000, "h": 3000, "max_h": 1200, "target_w": 0},
    {"name": "long_1728", "w": 1000, "h": 1728, "max_h": 1200, "target_w": 0},  # 单切片边界
    {"name": "narrow_4000", "w": 800, "h": 4000, "max_h": 1200, "target_w": 0},
]


def _spawn_sidecar():
    proc = subprocess.Popen(
        [sys.executable, str(SIDECAR_SCRIPT)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    return proc


def _read_line(stdout, timeout=10.0):
    import select
    deadline = time.time() + timeout
    while time.time() < deadline:
        r, _, _ = select.select([stdout], [], [], 0.1)
        if r:
            line = stdout.readline()
            if line:
                return json.loads(line)
        time.sleep(0.05)
    raise TimeoutError("sidecar 超时")


def _send(proc, req, timeout=30.0):
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    return _read_line(proc.stdout, timeout=timeout)


def _make_solid_image(path: Path, w: int, h: int, color=(255, 0, 0)):
    """创建纯色长图（用于缝隙检测时，缝是白色，分段间纯色不连续即可见）。"""
    Image.new("RGB", (w, h), color).save(path)


def _chrome_render_to_png(html_path: Path, png_path: Path, width: int = 700, height: int = 10000):
    """用 Chrome headless 渲染 HTML 到 PNG。"""
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "google-chrome",
        "chrome",
    ]
    chrome = None
    for p in chrome_paths:
        try:
            subprocess.run([p, "--version"], check=True, capture_output=True, timeout=2)
            chrome = p
            break
        except Exception:
            continue
    if chrome is None:
        pytest.skip("Chrome 未安装，跳过渲染验证")

    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        f"--screenshot={png_path}",
        f"--window-size={width},{height}",
        f"file://{html_path.resolve()}",
    ]
    subprocess.run(cmd, check=True, timeout=30, capture_output=True)


def _detect_white_gap_rows(png_path: Path, image_w: int = 650, image_h: int | None = None) -> int:
    """
    检测渲染图中图片内容区域是否有 1px 白色缝隙。

    Chrome 窗口宽度 = 700px，图片 display_w = 650px，左右各有 25px 页面 padding。
    只检查图片实际宽度范围内的行（x = (700-650)/2 = 25 到 675）。
    只检查图片实际高度范围内的行（y = 0 到 image_h），跳过截图窗口下方的空白。
    如果中间有连续白行 → 真 1px 缝隙（V5 修复项 #2 退化）。
    """
    img = Image.open(png_path).convert("RGB")
    w, h = img.size
    margin_x = (w - image_w) // 2
    x_start = margin_x
    x_end = w - margin_x
    y_end = image_h if image_h is not None else h
    y_end = min(y_end, h)
    px = img.load()
    white_rows = 0
    for y in range(y_end):
        is_white = all(px[x, y] == (255, 255, 255) for x in range(x_start, x_end))
        if is_white:
            white_rows += 1
    return white_rows


# ─────────────────────────────────────
# 4 真实场景 - 通过 Sidecar 端到端
# ─────────────────────────────────────

@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
def test_scenario_sidecar_assemble_returns_html(tmp_path, scenario):
    """4 真实场景：通过 Sidecar 切片 + 组装应返回有效 HTML。"""
    img_path = tmp_path / f"{scenario['name']}.png"
    _make_solid_image(img_path, scenario["w"], scenario["h"], color=(255, 0, 0))

    proc = _spawn_sidecar()
    try:
        _read_line(proc.stdout, timeout=3.0)  # ready
        slice_resp = _send(proc, {
            "id": "s1",
            "type": "image.slice",
            "params": {
                "path": str(img_path),
                "max_height": scenario["max_h"],
                "target_width": scenario["target_w"],
            },
        })
        assert slice_resp["ok"] is True
        slices = slice_resp["result"]["slices"]
        # 切片总高 = 原图高
        total_h = sum(s["height"] for s in slices)
        assert total_h == scenario["h"], f"{scenario['name']}: 切片总高 {total_h} != 原图 {scenario['h']}"

        asm_resp = _send(proc, {
            "id": "a1",
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
                "display_w": 650,
            },
        })
        assert asm_resp["ok"] is True, f"{scenario['name']}: assemble 失败: {asm_resp.get('error')}"
        html = asm_resp["result"]["html"]
        assert "<table" in html
        assert "</table>" in html
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["name"] for s in SCENARIOS])
def test_scenario_chrome_render_no_white_gap(tmp_path, scenario):
    """
    V5 黄金标准：4 场景 HTML 经 Chrome 渲染后零白线缝隙。
    红色长图切分时如果出现 1px 白线，扫描会检测到连续白行。
    """
    img_path = tmp_path / f"{scenario['name']}.png"
    _make_solid_image(img_path, scenario["w"], scenario["h"], color=(255, 0, 0))

    proc = _spawn_sidecar()
    try:
        _read_line(proc.stdout, timeout=3.0)
        slice_resp = _send(proc, {
            "id": "s1",
            "type": "image.slice",
            "params": {
                "path": str(img_path),
                "max_height": scenario["max_h"],
                "target_width": scenario["target_w"],
            },
        })
        assert slice_resp["ok"] is True
        slices = slice_resp["result"]["slices"]

        asm_resp = _send(proc, {
            "id": "a1",
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
                "display_w": 650,
            },
        })
        assert asm_resp["ok"] is True
        html = asm_resp["result"]["html"]

        # 写出 HTML
        html_path = tmp_path / f"{scenario['name']}.html"
        html_path.write_text(html, encoding="utf-8")

        # Chrome 渲染
        png_path = tmp_path / f"{scenario['name']}.png_render.png"
        render_h = sum(s["height"] for s in slices) + 100
        _chrome_render_to_png(html_path, png_path, width=700, height=min(render_h, 15000))

        # 检测白线
        image_h = sum(s["height"] for s in slices)
        white_rows = _detect_white_gap_rows(png_path, image_w=650, image_h=image_h)
        # V5 标准：图片区域内 0 白线 = 零缝隙
        assert white_rows == 0, (
            f"{scenario['name']} 渲染后图片区域内检测到 {white_rows} 行白线，"
            f"存在 1px 缝隙（V5 修复项 #2 退化）"
        )
    finally:
        proc.terminate()
        proc.wait(timeout=3.0)
