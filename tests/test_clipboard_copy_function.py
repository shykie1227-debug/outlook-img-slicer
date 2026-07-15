"""复制 HTML 到剪贴板的回归测试。

覆盖两个用户可感知目标：
1. 经典 Outlook 可以读取 CF_HTML，不会因为普通文本粘贴导致样式丢失。
2. 网页邮箱复制路径使用自包含 base64 图片，避免依赖本地临时文件。
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
    """剪贴板写入函数必须稳定可导入，供桌面 UI 的复制动作调用。"""
    assert callable(copy_cf_html_to_clipboard)


def test_copy_cf_html_writes_same_bytes_as_build_windows_clipboard_html():
    """mock win32clipboard：写入 CF_HTML 的字节 == build_windows_clipboard_html 产出。"""
    html = "<html><body><p>cliptest 中文</p></body></html>"
    raw = build_windows_clipboard_html(html)

    mock_wc = mock.MagicMock()
    html_format_id = 49301
    mock_wc.RegisterClipboardFormat.return_value = html_format_id
    mock_wcon = mock.MagicMock()
    mock_wcon.CF_UNICODETEXT = 13

    with mock.patch.dict(sys.modules, {"win32clipboard": mock_wc, "win32con": mock_wcon}):
        with mock.patch.object(outlook_sender.sys, "platform", "win32"):
            copy_cf_html_to_clipboard(raw)

    mock_wc.OpenClipboard.assert_called_once()
    # SetClipboardData 至少写入 CF_UNICODETEXT（兼容）与 CF_HTML
    set_calls = [tuple(c.args) for c in mock_wc.SetClipboardData.call_args_list]
    mock_wc.RegisterClipboardFormat.assert_called_once_with("HTML Format")
    assert (html_format_id, raw) in set_calls, "CF_HTML 写入字节与 build 产物不一致"
    mock_wc.CloseClipboard.assert_called_once()


def test_copy_cf_html_raises_runtime_error_on_non_windows():
    """非 Windows 平台必须明确抛 RuntimeError（不静默失败）。"""
    with mock.patch.object(outlook_sender.sys, "platform", "darwin"):
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
