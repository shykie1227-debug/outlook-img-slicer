"""
V4.7.9 剪贴板 HTML 回归测试

新版 Outlook for Windows 粘贴时可能读取 Windows 原生 CF_HTML，
不能只依赖 Qt 的 text/html MIME。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from main import _build_windows_clipboard_html, _extract_html_fragment  # noqa: E402


def _read_offset(payload: str, name: str) -> int:
    match = re.search(rf"^{name}:(\d+)\r?$", payload, flags=re.MULTILINE)
    assert match, f"{name} missing"
    return int(match.group(1))


def test_extract_html_fragment_uses_body_content():
    html = "<html><head><title>x</title></head><body><table><tr><td>img</td></tr></table></body></html>"

    assert _extract_html_fragment(html) == "<table><tr><td>img</td></tr></table>"


def test_windows_clipboard_html_offsets_are_valid():
    html = "<html><body><table><tr><td><img src='data:image/png;base64,xxx'></td></tr></table></body></html>"
    payload = _build_windows_clipboard_html(html).decode("utf-8")

    start_html = _read_offset(payload, "StartHTML")
    end_html = _read_offset(payload, "EndHTML")
    start_fragment = _read_offset(payload, "StartFragment")
    end_fragment = _read_offset(payload, "EndFragment")

    assert payload[start_html:end_html].startswith("<html><body>")
    assert payload[start_fragment:end_fragment].startswith("<table>")
    assert payload[start_fragment:end_fragment].endswith("</table>")
    assert "data:image/png;base64,xxx" in payload[start_fragment:end_fragment]


def test_copy_html_does_not_put_status_message_in_plain_text_fallback():
    main_src = (ROOT / "main.py").read_text(encoding="utf-8")
    copy_start = main_src.find("def _copy_html")
    assert copy_start >= 0
    copy_body = main_src[copy_start:main_src.find("\n    def _compress_slices", copy_start)]

    assert 'mime.setData("HTML Format", _build_windows_clipboard_html(html))' in copy_body
    assert "mime.setText(html)" in copy_body
    assert "已将 {len(self.slice_paths)} 张切片 HTML 复制到剪贴板" not in copy_body


def test_copy_html_does_not_materialize_twice():
    main_src = (ROOT / "main.py").read_text(encoding="utf-8")
    copy_start = main_src.find("def _copy_html")
    assert copy_start >= 0
    copy_body = main_src[copy_start:main_src.find("\n    def _compress_slices", copy_start)]

    assert "generate_plain_html(" in copy_body
    assert "materialize_display_slices_strict(" not in copy_body
