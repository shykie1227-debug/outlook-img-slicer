"""
V4.7.7 R3 修复 — build.py 依赖列表与 requirements.txt 一致性

历史 bug：
- v4.6.1 build.py 写死 pywin32==306
- Python 3.14 没有 pywin32 306 版本（只有 311/312）
- 导致 `python build.py` 整个 pip install 链卡死
- 用户在 Windows 10 (Python 3.14.5) 跑 build.py 报：
  ERROR: No matching distribution found for pywin32==306

修复：
- pywin32==306 → pywin32（不锁版本）
- import_to_pip 补 python-pptx / lxml（docstring 提了但漏）

本测试确保 build.py 未来不再退化（防"pywin32==306"再次写死）。
"""

import sys
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_build_py_no_hardcoded_pywin32_version():
    """V4.7.7 R3: build.py 不应有 pywin32==XXX 硬编码版本号"""
    build_src = (ROOT / "build.py").read_text()
    # 去除 docstring 和注释（以 # 或三引号 开头的行）
    code_lines = []
    in_docstring = False
    for line in build_src.split('\n'):
        stripped = line.strip()
        # 处理三引号 docstring
        if '"""' in stripped or "'''" in stripped:
            in_docstring = not in_docstring
            continue
        if in_docstring or stripped.startswith('#'):
            continue
        code_lines.append(line)
    code_only = '\n'.join(code_lines)
    # 任何 pywin32==N 模式都应被禁止
    matches = re.findall(r'pywin32[=<>!]+\d+', code_only)
    assert not matches, \
        f"build.py 可执行代码不应有 pywin32 硬编码版本号（防 Python 3.14+ 不兼容）: {matches}"


def test_build_py_import_to_pip_includes_python_pptx():
    """V4.7.7 R3: import_to_pip 应包含 python-pptx（V4.6.1 漏了）"""
    build_src = (ROOT / "build.py").read_text()
    # 找 import_to_pip 字典
    m = re.search(
        r'import_to_pip\s*=\s*\{(.*?)\}',
        build_src,
        re.DOTALL
    )
    assert m, "找不到 import_to_pip 字典"
    body = m.group(1)
    assert '"python-pptx"' in body or "'python-pptx'" in body, \
        "import_to_pip 必须包含 python-pptx 映射"


def test_build_py_import_to_pip_includes_lxml():
    """V4.7.7 R3: import_to_pip 应包含 lxml（V4.6.1 漏了）"""
    build_src = (ROOT / "build.py").read_text()
    m = re.search(
        r'import_to_pip\s*=\s*\{(.*?)\}',
        build_src,
        re.DOTALL
    )
    body = m.group(1)
    assert '"lxml"' in body or "'lxml'" in body, \
        "import_to_pip 必须包含 lxml 映射"


def test_build_py_pip_installs_pywin32_unpinned():
    """V4.7.7 R3: pip install 应使用 'pywin32'（不锁版本）"""
    build_src = (ROOT / "build.py").read_text()
    # 找 pip install 行的 pywin32 段
    m = re.search(r'pip_pkgs\s*=\s*.*?pywin32["\']?', build_src)
    assert m, "找不到 pip_pkgs 中的 pywin32"
    # pywin32 后面不应有 ==N
    after = build_src[m.end():m.end() + 20]
    assert not re.match(r'\s*==\d+', after), \
        f"pywin32 不应有 ==N 版本: '...{after}...'"


def test_requirements_txt_and_build_py_consistent():
    """V4.7.7 R3: requirements.txt 的所有包应都能在 build.py 装上"""
    reqs_text = (ROOT / "requirements.txt").read_text()
    # 提取 requirements.txt 里的包名（去掉版本约束）
    req_names = set()
    for line in reqs_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # 包名 = 第一个字母数字段
        m = re.match(r'([A-Za-z0-9_\-\.]+)', line)
        if m:
            req_names.add(m.group(1).lower())
    # 排除 UPX（不是 pip 包）
    req_names.discard('upx')

    build_src = (ROOT / "build.py").read_text()
    m = re.search(
        r'import_to_pip\s*=\s*\{(.*?)\}',
        build_src,
        re.DOTALL
    )
    body = m.group(1)
    # 找所有 pip 包名
    pip_names = set()
    for match in re.finditer(r'"([a-zA-Z0-9_\-\.]+)"', body):
        pip_names.add(match.group(1).lower())
    # 加 pywin32（是直接装不通过 import 检查的）
    pip_names.add('pywin32')

    # 关键检查：pywin32 在 requirements.txt，build.py 应能装
    assert 'pywin32' in req_names
    assert 'pywin32' in pip_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
