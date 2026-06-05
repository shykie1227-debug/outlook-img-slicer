"""
V4.7.7 Fix E 测试 — 干掉 mode_dialog，改面板 toggle 分流

修复目标：
1. 拖入文件不再弹 ProcessModeDialog
2. 面板 chk_export_mode 关闭（默认）= 切图模式
3. 面板 chk_export_mode 打开 = 导出图片模式
4. _on_export_mode_changed 状态变化有即时反馈
5. mode_dialog import 在 main.py 中已移除（避免死引用）
6. _handle_multi_files 死代码已移除
"""

import sys
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ════════════════════════════════════════════════════
# Fix E-1: chk_export_mode 控件存在 + 默认关闭
# ════════════════════════════════════════════════════

def test_chk_export_mode_widget_exists():
    """Fix E: 面板必须有 chk_export_mode toggle 控件"""
    main_src = (ROOT / "main.py").read_text()
    assert "self.chk_export_mode" in main_src, "缺 chk_export_mode 控件"
    assert "QCheckBox(\"🖼️ 导出图片\")" in main_src, "toggle 文案应为「🖼️ 导出图片」"


def test_chk_export_mode_default_unchecked():
    """Fix E: chk_export_mode 默认未勾选（= 切图模式）"""
    main_src = (ROOT / "main.py").read_text()
    # 找 chk_export_mode 初始化块
    m = re.search(
        r'self\.chk_export_mode\.setChecked\(([^)]+)\)',
        main_src
    )
    assert m, "找不到 setChecked 调用"
    # 默认应该是 False
    assert "False" in m.group(1), f"默认值应为 False（= 切图），实际: {m.group(1)}"


def test_chk_export_mode_has_callback():
    """Fix E: chk_export_mode 必须绑定 stateChanged 回调"""
    main_src = (ROOT / "main.py").read_text()
    assert "chk_export_mode.stateChanged.connect(self._on_export_mode_changed)" in main_src, \
        "缺 _on_export_mode_changed 绑定"


# ════════════════════════════════════════════════════
# Fix E-2: _on_export_mode_changed 反馈
# ════════════════════════════════════════════════════

def test_on_export_mode_changed_has_feedback():
    """Fix E: 模式切换必须有即时状态反馈"""
    main_src = (ROOT / "main.py").read_text()
    # 找 _on_export_mode_changed 函数
    m = re.search(
        r'def _on_export_mode_changed\(self,[^)]*\):.*?(?=\n    def |\nclass )',
        main_src,
        re.DOTALL
    )
    assert m, "找不到 _on_export_mode_changed 函数"
    body = m.group(0)
    # 两条状态都需要有 self._set_status
    assert body.count("self._set_status") >= 2, "模式切换应有 2+ 次状态反馈"


# ════════════════════════════════════════════════════
# Fix E-3: 拖入流程不再弹 ProcessModeDialog
# ════════════════════════════════════════════════════

def test_handle_dropped_files_no_dialog():
    """Fix E: _handle_dropped_files 不再实例化 + 弹 ProcessModeDialog"""
    main_src = (ROOT / "main.py").read_text()
    # 找 _handle_dropped_files 函数体
    m = re.search(
        r'def _handle_dropped_files\(self,[^)]*\):.*?(?=\n    def |\nclass )',
        main_src,
        re.DOTALL
    )
    assert m, "找不到 _handle_dropped_files 函数"
    body = m.group(0)
    # 检测是否还有「实例化 + exec()」的弹窗调用（注释不算）
    # 模式：ProcessModeDialog(...).exec() 或 dlg.exec()
    assert "ProcessModeDialog(" not in body, \
        "_handle_dropped_files 不应再实例化 ProcessModeDialog"
    # dlg.exec() 模式（间接实例化）
    assert not re.search(r"dlg\s*=\s*ProcessModeDialog", body), \
        "_handle_dropped_files 不应再赋值 dlg = ProcessModeDialog"


def test_handle_dropped_files_uses_toggle_state():
    """Fix E: _handle_dropped_files 必须根据 chk_export_mode.isChecked() 分流"""
    main_src = (ROOT / "main.py").read_text()
    m = re.search(
        r'def _handle_dropped_files\(self,[^)]*\):.*?(?=\n    def |\nclass )',
        main_src,
        re.DOTALL
    )
    body = m.group(0)
    assert "self.chk_export_mode.isChecked()" in body, \
        "必须根据 chk_export_mode.isChecked() 分流"


def test_handle_dropped_files_no_mode_dialog_import():
    """Fix E: main.py 不再 import mode_dialog"""
    main_src = (ROOT / "main.py").read_text()
    # 找 import 段
    import re as _re
    m = _re.search(r'from mode_dialog import.*', main_src)
    assert not m, f"main.py 不应再 import mode_dialog: {m.group(0) if m else ''}"


# ════════════════════════════════════════════════════
# Fix E-4: 死代码清理
# ════════════════════════════════════════════════════

def test_handle_multi_files_removed():
    """Fix E: _handle_multi_files 死代码已移除"""
    main_src = (ROOT / "main.py").read_text()
    assert "def _handle_multi_files" not in main_src, \
        "_handle_multi_files 死代码应已移除"


def test_mode_constants_removed_from_main():
    """Fix E: MODE_SLICE / MODE_EXPORT / SORT_* 常量不再在 main.py 中使用"""
    main_src = (ROOT / "main.py").read_text()
    for const in ("MODE_SLICE", "MODE_EXPORT", "SORT_NATURAL", "SORT_DRAG_ORDER"):
        assert const not in main_src, f"{const} 应已从 main.py 移除"


# ════════════════════════════════════════════════════
# Fix E-5: mode_dialog.py 文件本身保留（向后兼容）
# ════════════════════════════════════════════════════

def test_mode_dialog_file_preserved():
    """Fix E: mode_dialog.py 文件本身保留（用户回退需要）"""
    assert (ROOT / "mode_dialog.py").exists(), "mode_dialog.py 文件应保留"


# ════════════════════════════════════════════════════
# Fix E-6: 行为流（拖入 → 切图模式 → 不弹窗）
# ════════════════════════════════════════════════════

def test_slice_mode_path_single_file():
    """Fix E: 切图模式 + 单文件 → 直接 _start_processing"""
    main_src = (ROOT / "main.py").read_text()
    m = re.search(
        r'def _handle_dropped_files\(self,[^)]*\):.*?(?=\n    def |\nclass )',
        main_src,
        re.DOTALL
    )
    body = m.group(0)
    # 切图分支 + 单文件 → _start_processing
    assert "self._start_processing(valid[0])" in body, \
        "切图模式单文件应直接调 _start_processing"


def test_slice_mode_path_multi_file():
    """Fix E: 切图模式 + 多文件 → 仅处理第一张 + 状态栏提示"""
    main_src = (ROOT / "main.py").read_text()
    m = re.search(
        r'def _handle_dropped_files\(self,[^)]*\):.*?(?=\n    def |\nclass )',
        main_src,
        re.DOTALL
    )
    body = m.group(0)
    # 多文件分支必须引导用户切到导出模式
    assert "导出图片" in body and "打开右上角" in body, \
        "多文件切图模式应提示用户切到导出模式"


def test_export_mode_path():
    """Fix E: 导出模式 → ExportFormatDialog"""
    main_src = (ROOT / "main.py").read_text()
    m = re.search(
        r'def _handle_dropped_files\(self,[^)]*\):.*?(?=\n    def |\nclass )',
        main_src,
        re.DOTALL
    )
    body = m.group(0)
    assert "ExportFormatDialog" in body, "导出模式应弹 ExportFormatDialog"
    assert "self._export_images(" in body, "导出模式应调 _export_images"


# ════════════════════════════════════════════════════
# Fix E-7: R2 架构师审查抓出的 3 个真问题
# ════════════════════════════════════════════════════

def test_on_export_mode_changed_no_ambiguous_ternary():
    """R2 架构师：原 if state == Qt.Checked.value if hasattr(...) else (state == Qt.Checked) 意图不清
    修复后应简化为 bool(state)"""
    main_src = (ROOT / "main.py").read_text()
    m = re.search(
        r'def _on_export_mode_changed\(self,[^)]*\):.*?(?=\n    def |\nclass )',
        main_src,
        re.DOTALL
    )
    body = m.group(0)
    assert "if bool(state):" in body, "状态判断应简化为 `if bool(state):`"
    # 旧代码有问题的三元嵌套
    assert "Qt.Checked.value if hasattr" not in body, "旧三元嵌套已修复"


def test_auto_merge_images_import_removed():
    """R2 架构师：auto_merge_images 死 import 应已删除"""
    main_src = (ROOT / "main.py").read_text()
    # 顶层 import 段不应再有 auto_merge_images
    import_lines = [l for l in main_src.split('\n')[:50] if l.startswith('from image_slicer')]
    assert len(import_lines) == 1, "顶层应有且仅有 1 行 image_slicer import"
    assert 'auto_merge_images' not in import_lines[0], \
        f"auto_merge_images 死 import 应已移除: {import_lines[0]}"


def test_export_filename_uses_full_timestamp():
    """R2 架构师：文件名后缀应使用完整时间戳（int(time.time())）
    避免 1 秒内同 pid 重复"""
    main_src = (ROOT / "main.py").read_text()
    # 全文件扫描：找包含 int(time.time() 的行
    ts_lines = [l for l in main_src.split('\n') if 'int(time.time()' in l]
    assert ts_lines, "main.py 应有使用 int(time.time() 的代码行"
    for line in ts_lines:
        # 任何使用 int(time.time()) 的行都不应有 % 100000
        assert "% 100000" not in line, \
            f"int(time.time()) 不应取模，1秒内可能重名: {line.strip()}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
