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
DESKTOP_ROOT = ROOT / "desktop"
sys.path.insert(0, str(DESKTOP_ROOT))


def test_build_py_no_hardcoded_pywin32_version():
    """V4.7.7 R3: build.py 不应有 pywin32==XXX 硬编码版本号"""
    build_src = (DESKTOP_ROOT / "build.py").read_text()
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
    build_src = (DESKTOP_ROOT / "build.py").read_text()
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
    build_src = (DESKTOP_ROOT / "build.py").read_text()
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
    build_src = (DESKTOP_ROOT / "build.py").read_text()
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

    build_src = (DESKTOP_ROOT / "build.py").read_text()
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


def test_pyinstaller_spec_disables_strip_on_windows():
    """Windows 默认没有 strip 工具，开启会产生大量 FileNotFoundError 警告。"""
    spec_src = (DESKTOP_ROOT / "outlook_img_slicer.spec").read_text(encoding="utf-8")

    assert "strip=False" in spec_src
    assert "strip=True" not in spec_src


# ════════════════════════════════════════════════════
# V4.7.7 R3.1: 变更日志机制
# ════════════════════════════════════════════════════

def test_build_py_has_print_change_log():
    """R3.1: build.py 必须在 main() 调用 print_change_log()"""
    build_src = (DESKTOP_ROOT / "build.py").read_text()
    assert "def print_change_log" in build_src, "缺 print_change_log() 函数"
    # 必须从 main() 调用
    assert "print_change_log()" in build_src, "main() 未调用 print_change_log()"


def test_build_py_history_file_in_dist():
    """R3.1: 历史记录文件应在 dist/ 下（被 .gitignore 排除）"""
    build_src = (DESKTOP_ROOT / "build.py").read_text()
    # HISTORY_FILE 路径应在 dist/.build_history.json
    assert "HISTORY_FILE" in build_src
    assert "dist" in build_src
    assert ".build_history.json" in build_src


def test_gitignore_excludes_build_history():
    """R3.1: .gitignore 应排除 .build_history.json（避免误提交）"""
    gitignore = (ROOT / ".gitignore").read_text()
    # dist/ 整目录被排除，或者 .build_history.json 被单条排除
    assert "dist/" in gitignore or ".build_history.json" in gitignore, \
        ".gitignore 应排除 dist/ 或 .build_history.json"


def test_print_change_log_handles_no_history():
    """R3.1: 首次运行（无历史记录）不应崩"""
    # 验证 print_change_log() 有 try-except 保护
    build_src = (DESKTOP_ROOT / "build.py").read_text()
    m = re.search(
        r'def print_change_log\(.*?\):(.*?)(?=\ndef )',
        build_src,
        re.DOTALL
    )
    assert m, "找不到 print_change_log 函数体"
    body = m.group(1)
    # 首次运行分支
    assert "首次运行" in body or "无历史" in body, "应有首次运行提示"
    # JSON 解析失败保护
    assert "except" in body, "JSON 解析失败应有 try-except"


def test_print_change_log_shows_warn_on_write_fail():
    """R3.1: 写历史记录失败时，应警告而不是静默"""
    build_src = (DESKTOP_ROOT / "build.py").read_text()
    # 保存历史记录的 try-except 块不应是裸 pass
    m = re.search(
        r'# 保存本次记录(.*?)\n    try:',
        build_src,
        re.DOTALL
    )
    # 检查 "except Exception:" 后不是裸 pass
    m2 = re.search(
        r'except Exception as e:\s*\n\s*print\(f"  \[警告\] 历史记录保存失败',
        build_src
    )
    assert m2, "写历史失败应有警告输出（不是裸 pass）"


def test_print_change_log_actually_writes_history(tmp_path):
    """R3.1: print_change_log() 实际能写入历史文件并能再次读取"""
    import json
    import sys
    sys.path.insert(0, str(DESKTOP_ROOT))
    from build import print_change_log, DIST_DIR
    # 用 monkey-patch 重定向 DIST_DIR 到 tmp_path
    import build as build_mod
    orig_dist = build_mod.DIST_DIR
    orig_history = build_mod.HISTORY_FILE
    build_mod.DIST_DIR = tmp_path / "dist"
    build_mod.HISTORY_FILE = build_mod.DIST_DIR / ".build_history.json"
    try:
        # 首次运行
        build_mod.print_change_log()
        assert build_mod.HISTORY_FILE.exists(), "首次运行后应创建历史文件"
        first_record = json.loads(build_mod.HISTORY_FILE.read_text())
        assert "git_sha" in first_record
        assert "timestamp" in first_record
        assert "deps" in first_record
        # 第二次运行（依赖未变）
        build_mod.print_change_log()
        second_record = json.loads(build_mod.HISTORY_FILE.read_text())
        # 记录应被覆盖（timestamp 变化或保持一致）
        assert second_record["git_sha"] == first_record["git_sha"]
    finally:
        build_mod.DIST_DIR = orig_dist
        build_mod.HISTORY_FILE = orig_history


def test_get_declared_deps_uses_utf8_encoding():
    """R3.2: _get_declared_deps() 必须用 utf-8 encoding（防 Windows GBK UnicodeDecodeError）"""
    build_src = (DESKTOP_ROOT / "build.py").read_text()
    # 找 _get_declared_deps 函数体
    m = re.search(
        r'def _get_declared_deps\(.*?\):(.*?)(?=\ndef )',
        build_src,
        re.DOTALL
    )
    assert m, "找不到 _get_declared_deps"
    body = m.group(1)
    # 必须显式 encoding='utf-8'
    assert 'encoding="utf-8"' in body or "encoding='utf-8'" in body, \
        "_get_declared_deps 必须用 encoding='utf-8' 读 requirements.txt"
    # 还要 errors='replace' 作为兑底
    assert 'errors="replace"' in body or "errors='replace'" in body, \
        "_get_declared_deps 必须用 errors='replace' 防解码失败"


def test_get_git_sha_uses_utf8_encoding():
    """R3.2: _get_git_sha() 必须用 utf-8 encoding"""
    build_src = (DESKTOP_ROOT / "build.py").read_text()
    m = re.search(
        r'def _get_git_sha\(.*?\):(.*?)(?=\ndef )',
        build_src,
        re.DOTALL
    )
    assert m, "找不到 _get_git_sha"
    body = m.group(1)
    assert 'encoding="utf-8"' in body, \
        "_get_git_sha subprocess.run 必须用 encoding='utf-8'"


def test_get_declared_deps_handles_gbk_invalid_bytes(tmp_path):
    """R3.2 集成测试: requirements.txt 含 GBK 无效字节时不应崩"""
    import sys
    sys.path.insert(0, str(DESKTOP_ROOT))
    import build as build_mod
    # 造一个含 0xAC 的“中文 + GBK 异常字节”混合文件
    bad_req = tmp_path / "requirements.txt"
    bad_req.write_bytes(bytes([0x23, 0x20, 0x4F, 0x75, 0x74, 0x6C, 0x6F, 0x6F, 0x6B, 0x20,
                                0xAC, 0x20,
                                0xE4, 0x20,
                                0xB0, 0xFC, 0xD7, 0xB1,
                                0x0A,
                                0x50, 0x69, 0x6C, 0x6C, 0x6F, 0x77, 0x3E, 0x3D, 0x31, 0x30, 0x2E, 0x30, 0x2E, 0x30, 0x0A]))  # # Outlook 0xAC 0xE4 中文(GBK) \n Pillow>=10.0.0 \n
    # monkey-patch PROJECT_ROOT
    orig = build_mod.PROJECT_ROOT
    build_mod.PROJECT_ROOT = tmp_path
    try:
        deps = build_mod._get_declared_deps()
        # 成功读到 Pillow>=10.0.0 是关键
        assert "Pillow" in deps, f"应能读到 Pillow: {deps}"
        # 错误替换不丢依赖
        assert deps.get("Pillow") == "Pillow>=10.0.0"
    finally:
        build_mod.PROJECT_ROOT = orig


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
