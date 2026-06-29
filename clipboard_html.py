"""Windows CF_HTML helpers for Outlook and Word clipboard consumers."""

import re


def extract_html_fragment(html: str) -> str:
    """Return the content inside <body>, or the original string if no body exists."""
    body_match = re.search(
        r"<body\b[^>]*>(.*)</body>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return body_match.group(1) if body_match else html


def build_windows_clipboard_html(html: str) -> bytes:
    """Build a byte-correct UTF-8 CF_HTML payload."""
    fragment = extract_html_fragment(html)
    prefix = "<html><body><!--StartFragment-->"
    suffix = "<!--EndFragment--></body></html>"
    body = f"{prefix}{fragment}{suffix}"
    body_bytes = body.encode("utf-8")

    header_template = (
        "Version:0.9\r\n"
        "StartHTML:{start_html:010d}\r\n"
        "EndHTML:{end_html:010d}\r\n"
        "StartFragment:{start_fragment:010d}\r\n"
        "EndFragment:{end_fragment:010d}\r\n"
        "SourceURL:about:blank\r\n"
    )
    placeholder_header = header_template.format(
        start_html=0,
        end_html=0,
        start_fragment=0,
        end_fragment=0,
    )
    start_html = len(placeholder_header.encode("ascii"))
    start_fragment = start_html + len(prefix.encode("utf-8"))
    end_fragment = start_fragment + len(fragment.encode("utf-8"))
    end_html = start_html + len(body_bytes)
    header = header_template.format(
        start_html=start_html,
        end_html=end_html,
        start_fragment=start_fragment,
        end_fragment=end_fragment,
    )
    return header.encode("ascii") + body_bytes
