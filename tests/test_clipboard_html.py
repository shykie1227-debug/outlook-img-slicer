import re

from main import _build_windows_clipboard_html


def _offsets(payload: bytes) -> dict[str, int]:
    header = payload.split(b"<html>", 1)[0].decode("ascii")
    return {
        name: int(value)
        for name, value in re.findall(
            r"(StartHTML|EndHTML|StartFragment|EndFragment):(\d+)",
            header,
        )
    }


def test_cf_html_offsets_use_utf8_bytes_for_chinese_fragment():
    payload = _build_windows_clipboard_html(
        "<html><body><p>按钮中文测试</p></body></html>"
    )
    offsets = _offsets(payload)

    assert payload[offsets["StartHTML"]:].startswith(b"<html>")
    assert payload[offsets["StartFragment"]:].startswith("<p>按钮".encode("utf-8"))
    assert payload[offsets["EndFragment"]:].startswith(b"<!--EndFragment-->")
    assert offsets["EndHTML"] == len(payload)


def test_cf_html_fragment_boundaries_preserve_complete_html():
    fragment = '<table><tr><td><img alt="中文长图" /></td></tr></table>'
    payload = _build_windows_clipboard_html(f"<html><body>{fragment}</body></html>")
    offsets = _offsets(payload)

    copied = payload[offsets["StartFragment"]:offsets["EndFragment"]]
    assert copied.decode("utf-8") == fragment
