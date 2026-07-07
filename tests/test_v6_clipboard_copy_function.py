"""
V6 复制路径修复 2-D 回归测试

覆盖 Fix 2-B（补齐缺失的 copy_cf_html_to_clipboard，消除 sidecar outlook.copyClipboard
的 ImportError）+ Fix 2-A（复制 = 网页邮箱自包含 base64）：

  1. outlook_sender.copy_cf_html_to_clipboard 存在且可导入（不再 ImportError）。
  2. 在 mock win32clipboard 环境下，函数被调用且写入的 CF_HTML 字节与
     clipboard_html.build_windows_clipboard_html 完全一致（验证
     html.clipboard → outlook.copyClipboard 链路不再 ImportError）。
  3. 非 Windows 平台（如 macOS CI）必须抛 RuntimeError（明确提示）。
  4. generate_plain_html 产出的 <img src="data:image/...;base64,..."> 存在
     （网页邮箱路径自包含）。
"""
import sys
from pathlib import Path
from unittest import mock

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clipboard_html import build_windows_clipboard_html
import outlook_sender
from outlook_sender import copy_cf_html_to_clipboard
from html_assembler import generate_plain_html, SliceItem
from clickable_map import Hotspot
from hotspot_slicer import slice_paths_by_hotspots


def test_copy_cf_html_function_is_importable():
    """Fix 2-B：函数已定义，sidecar 的 `from outlook_sender import copy_cf_html_to_clipboard`
    不再 ImportError。"""
    assert callable(copy_cf_html_to_clipboard)


def test_copy_cf_html_writes_same_bytes_as_build_windows_clipboard_html():
    """mock win32clipboard：写入 CF_HTML 的字节 == build_windows_clipboard_html 产出。"""
    html = "<html><body><p>cliptest 中文</p></body></html>"
    raw = build_windows_clipboard_html(html)

    mock_wc = mock.MagicMock()
    mock_wc.CF_HTML = "HTML Format"  # win32clipboard.CF_HTML 内置常量
    mock_wcon = mock.MagicMock()
    mock_wcon.CF_UNICODETEXT = 13

    with mock.patch.dict(sys.modules, {"win32clipboard": mock_wc, "win32con": mock_wcon}):
        with mock.patch.object(outlook_sender.sys, "platform", "win32"):
            copy_cf_html_to_clipboard(raw)

    mock_wc.OpenClipboard.assert_called_once()
    # SetClipboardData 至少写入 CF_UNICODETEXT（兼容）与 CF_HTML
    set_calls = [tuple(c.args) for c in mock_wc.SetClipboardData.call_args_list]
    assert (mock_wc.CF_HTML, raw) in set_calls, "CF_HTML 写入字节与 build 产物不一致"
    mock_wc.CloseClipboard.assert_called_once()


def test_copy_cf_html_raises_runtime_error_on_non_windows():
    """非 Windows 平台必须明确抛 RuntimeError（不静默失败）。"""
    with pytest.raises(RuntimeError):
        copy_cf_html_to_clipboard(b"x")


def test_generate_plain_html_embeds_base64_for_webmail(tmp_path):
    """Fix 2-A：复制路径保留自包含 base64 内联（网页邮箱可用）。"""
    src = tmp_path / "g.png"
    Image.new("RGB", (1000, 1000), (200, 200, 200)).save(src)
    hotspots = {src.name: [Hotspot(100, 100, 400, 400, "https://a.example")]}
    sliced, link_map = slice_paths_by_hotspots(
        [str(src)], hotspots, source_index_map={src.name: 1.0}
    )
    slices = [
        SliceItem(path=p, href=link_map.get(Path(p).name), sort_key=k, original_width=1000)
        for p, k in sliced
    ]
    html = generate_plain_html(slices, 960)
    assert "data:image/" in html and ";base64," in html
    assert "cid:" not in html
