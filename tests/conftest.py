"""Pytest path setup for the desktop PySide layout."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_UI = ROOT / "desktop"

for path in (DESKTOP_UI,):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


@pytest.fixture(scope="session")
def qapp():
    """
    会话级 QApplication（唯一、且全程存活）。

    为什么必须是 session 作用域：
      QApplication 一旦被 Python GC 回收，Qt 的全局应用指针就失效，
      之后任何 QWidget 构造都会**段错误**（而不是抛异常）。
      各测试文件原先各自写 module 作用域的 `qapp`，
      最先创建它的那个模块结束时引用计数归零 → 应用被销毁 →
      后续模块 new QWidget() 时崩溃。
      实测现场：tests/test_canvas_origin_alignment.py 按文件名排序在
      test_v491_hotspot_disabled.py 之前运行，前者模块结束时销毁了应用，
      后者在 desktop/main.py:502 的 super().__init__() 段错误。
      fixture 缓存在会话期间一直持有引用，应用不会再被回收。

    需要 QApplication 的测试直接把它作为参数即可；不要在本文件之外
    再定义 module/function 作用域的 `qapp`（会 shadow 掉这个会话级的）。
    """
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
