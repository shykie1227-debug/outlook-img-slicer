"""
V4.7.7 修复 — 补 main.py 顶层缺失的 import

3 轮专家审查时安全审查 subagent 在 30s 内抓出：
  ⚠️ `time` is NOT imported in main.py but `time.time()` is used
  ⚠️ `traceback` 在 try/except 块内局部 import，风格不一致

修复：
  - main.py 顶层加 `import time`
  - main.py 顶层加 `import traceback`
  - _export_images 内的 `import traceback` 删掉（用顶层）

本测试文件作为回归保护：未来再有人在 main.py 删 import 会立即被抓出。
"""

import sys
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _get_top_level_imports(py_path: Path) -> set:
    """提取 .py 文件顶层 import 的所有模块名"""
    tree = ast.parse(py_path.read_text())
    imports = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(alias.asname or alias.name)
    return imports


def test_main_py_imports_time():
    """V4.7.7 审查发现：main.py 用了 time.time() 但缺 import time"""
    imports = _get_top_level_imports(ROOT / "main.py")
    assert "time" in imports, "main.py 顶层必须 import time（_export_images 用 time.time()）"


def test_main_py_imports_traceback():
    """V4.7.7 审查发现：main.py 用了 traceback.format_exc() 但只在 try 块内局部 import"""
    imports = _get_top_level_imports(ROOT / "main.py")
    assert "traceback" in imports, "main.py 顶层必须 import traceback"


def test_main_py_no_local_traceback_import():
    """V4.7.7 修复：_export_images 内的 `import traceback` 局部 import 应已删除"""
    main_src = (ROOT / "main.py").read_text()
    # 局部 import traceback 只在 _export_images 内，旧代码有
    # 修复后应已移到顶层
    import re
    # 找 try/except 内的局部 import traceback
    assert "import traceback" not in main_src or main_src.count("import traceback") == 1, \
        "main.py 中 'import traceback' 应只在顶层出现一次"


def test_main_py_uses_time_correctly():
    """V4.7.7 验证：time.time() 调用存在（验证修复没破坏现有功能）"""
    main_src = (ROOT / "main.py").read_text()
    assert "time.time()" in main_src, "_export_images 缺 time.time() 调用"


def test_main_py_uses_traceback_correctly():
    """V4.7.7 验证：traceback.format_exc() 调用存在"""
    main_src = (ROOT / "main.py").read_text()
    assert "traceback.format_exc()" in main_src, "_export_images 缺 traceback.format_exc()"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
