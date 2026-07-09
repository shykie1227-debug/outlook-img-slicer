from pathlib import Path
import re

import main
import export_dialog
import hotspot_editor


ROOT = Path(__file__).resolve().parent.parent


def test_runtime_window_icon_resolves_to_current_root_icon():
    """运行时窗口图标必须使用当前根目录 icon.ico，而不是旧目录残留。"""
    icon_path = Path(main._resource_file("icon.ico"))

    assert icon_path.exists()
    assert icon_path.resolve() == (ROOT / "icon.ico").resolve()


def test_pyinstaller_spec_bundles_runtime_window_icon():
    """EXE 图标和运行时窗口图标都必须来自当前 icon.ico。"""
    spec = (ROOT / "desktop" / "outlook_img_slicer.spec").read_text(encoding="utf-8")

    assert 'icon=os.path.join(ROOT_DIR, "icon.ico")' in spec
    assert '(os.path.join(ROOT_DIR, "icon.ico"), ".")' in spec


def test_all_ui_icon_references_have_svg_files():
    """UI 中引用的图标必须存在，避免按钮/提示图标在 EXE 中空白。"""
    referenced = set()
    for rel in [
        "desktop/main.py",
        "desktop/hotspot_editor.py",
        "desktop/export_dialog.py",
    ]:
        referenced.update(
            re.findall(r'_icon\("([^"]+)"', (ROOT / rel).read_text(encoding="utf-8"))
        )

    missing = sorted(
        name for name in referenced if not (ROOT / "icons" / f"{name}.svg").exists()
    )

    assert not missing


def test_dialog_icon_loaders_resolve_root_icons():
    """导出/热区弹窗不能从不存在的 desktop/icons 读取图标。"""
    for module, icon_name in [
        (export_dialog, "arrow-down-to-line-white"),
        (export_dialog, "folder-open"),
        (hotspot_editor, "check-white"),
    ]:
        assert not module._icon(icon_name).isNull(), f"{module.__name__}:{icon_name}"
