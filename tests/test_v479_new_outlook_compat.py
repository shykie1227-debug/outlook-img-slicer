"""
V4.7.9 新 Outlook 兼容性提示回归测试

新版 Outlook for Windows（WebView2 版）不暴露经典 Outlook.Application COM。
发送失败时必须给出可执行的提示，而不是只显示 pywin32 原始异常。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from outlook_sender import (  # noqa: E402
    NEW_OUTLOOK_UNSUPPORTED_HINT,
    _is_new_outlook_automation_error,
)


def test_detects_common_new_outlook_com_registration_errors():
    samples = [
        Exception("Invalid class string: Outlook.Application"),
        Exception("Class not registered"),
        Exception("无效的类字符串"),
        Exception("类没有注册"),
        Exception("server execution failed"),
    ]

    assert all(_is_new_outlook_automation_error(exc) for exc in samples)


def test_new_outlook_hint_is_actionable():
    assert "新版 Outlook for Windows" in NEW_OUTLOOK_UNSUPPORTED_HINT
    assert "COM/MAPI" in NEW_OUTLOOK_UNSUPPORTED_HINT
    assert "经典 Outlook" in NEW_OUTLOOK_UNSUPPORTED_HINT
    assert "复制 HTML" in NEW_OUTLOOK_UNSUPPORTED_HINT
    assert "保存切图" in NEW_OUTLOOK_UNSUPPORTED_HINT
