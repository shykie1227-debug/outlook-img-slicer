"""
V4.7.8 R4 测试 — 多图降级提示醒目化

修复目标：解决 R2 架构师审查遗留的第 4 个 UX 风险
- 原 V4.7.7 Fix E: 仅 _set_status 多行文本（用户可能错过）
- V4.7.8: 保留状态栏提示 + 新增模态 QMessageBox.information 二次确认
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_version_bumped_to_v48():
    """VERSION 常量应升级到 4.8"""
    main_src = (ROOT / "main.py").read_text()
    m = re.search(r'VERSION\s*=\s*["\']([^"\']+)["\']', main_src)
    assert m, "找不到 VERSION 常量"
    assert m.group(1) == "4.8", f"VERSION 应为 4.8，实际: {m.group(1)}"


def test_multi_file_path_has_qmessagebox():
    """R4: 多文件切图分支应同时使用 _set_status + QMessageBox.information"""
    main_src = (ROOT / "main.py").read_text()
    # 找 _handle_dropped_files 函数体
    m = re.search(
        r'def _handle_dropped_files\(self,[^)]*\):.*?(?=\n    def |\nclass )',
        main_src,
        re.DOTALL
    )
    assert m, "找不到 _handle_dropped_files 函数"
    body = m.group(0)
    # 必须有 QMessageBox.information（模态提示）
    assert "QMessageBox.information(" in body, \
        "R4: 多图分支应使用 QMessageBox.information 模态提示"
    # 必须保留 _set_status（状态栏）
    assert "_set_status" in body, "R4: 应保留 _set_status 状态栏提示"
    # 标题应带 emoji
    assert "🖼️" in body, "R4: QMessageBox 标题应带 emoji 提高醒目度"


def test_multi_file_message_includes_count():
    """R4: QMessageBox 文案应包含总张数 + 引导用户切到导出模式"""
    main_src = (ROOT / "main.py").read_text()
    # 找 QMessageBox.information 调用块（手动平衡括号）
    start = main_src.find("QMessageBox.information(")
    assert start >= 0, "找不到 QMessageBox.information 调用"
    # 手动扫到匹配的 ) 配对结束
    depth = 0
    in_str = False
    quote_char = None
    triple = False
    i = start + len("QMessageBox.information(")
    end = -1
    while i < len(main_src):
        ch = main_src[i]
        if in_str:
            if ch == '\\' and i + 1 < len(main_src):
                i += 2
                continue
            if triple:
                if main_src[i:i+3] == quote_char * 3:
                    in_str = False
                    i += 3
                    continue
            else:
                if ch == quote_char:
                    in_str = False
        else:
            if ch in '"\'':
                # 探测三引号
                if main_src[i:i+3] == ch * 3:
                    in_str = True
                    triple = True
                    quote_char = ch
                    i += 3
                    continue
                in_str = True
                triple = False
                quote_char = ch
            elif ch == '(':
                depth += 1
            elif ch == ')':
                if depth == 0:
                    end = i + 1
                    break
                depth -= 1
        i += 1
    assert end > 0, "无法匹配 QMessageBox.information 闭合 )"
    call = main_src[start:end]
    # 应包含 len(valid) 引用张数
    assert "len(valid)" in call, f"R4: QMessageBox 文案应包含 len(valid) 张数: {call}"
    # 应引导用户切到导出模式
    assert "导出图片" in call, f"R4: QMessageBox 应引导用户切到导出模式: {call}"


def test_r4_does_not_break_fix_e():
    """R4: 不应破坏 V4.7.7 Fix E 已修复的 3 个真问题"""
    main_src = (ROOT / "main.py").read_text()
    # Fix E-1: chk_export_mode 控件 + toggle 文案
    assert "self.chk_export_mode" in main_src
    assert "QCheckBox(\"🖼️ 导出图片\")" in main_src
    # Fix E-2: _on_export_mode_changed 反馈 (>= 2 次 _set_status)
    m = re.search(
        r'def _on_export_mode_changed\(self,[^)]*\):.*?(?=\n    def |\nclass )',
        main_src,
        re.DOTALL
    )
    body = m.group(0)
    assert body.count("self._set_status") >= 2
    # Fix E-3: 拖入不再弹 ProcessModeDialog
    m = re.search(
        r'def _handle_dropped_files\(self,[^)]*\):.*?(?=\n    def |\nclass )',
        main_src,
        re.DOTALL
    )
    body = m.group(0)
    assert "ProcessModeDialog(" not in body
    # Fix E-7: bool(state) 简化
    m = re.search(
        r'def _on_export_mode_changed\(self,[^)]*\):.*?(?=\n    def |\nclass )',
        main_src,
        re.DOTALL
    )
    body = m.group(0)
    assert "if bool(state):" in body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
