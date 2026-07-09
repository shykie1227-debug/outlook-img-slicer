import pytest
from PIL import Image
import tempfile
from pathlib import Path

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication

from main import MainWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_classic_outlook_defaults_are_clear(qapp):
    win = MainWindow()
    try:
        assert win.edit_width.text() == "960"
        assert win.chk_smart.text() == "避开文字切图（推荐）"
        assert win.btn_send.text() == " 在 Outlook 中创建邮件"
    finally:
        win.close()


def test_status_has_only_one_semantic_icon(qapp):
    win = MainWindow()
    try:
        win._set_status("✅ 邮件窗口已打开，请检查后发送", "success")
        assert win.status_label.text() == "✅ 邮件窗口已打开，请检查后发送"
    finally:
        win.close()


def test_initial_status_explains_the_next_step(qapp):
    win = MainWindow()
    try:
        assert "拖入" in win.status_label.text()
        assert "经典 Outlook" in win.status_label.text()
    finally:
        win.close()


def test_feature_guide_and_manual_cut_button_are_discoverable(qapp):
    win = MainWindow()
    try:
        assert "1  放入文件" in win.guide_label.text()
        assert "2  调整切线 / 添加链接" in win.guide_label.text()
        assert "3  创建邮件" in win.guide_label.text()
        assert win.btn_adjust_cuts.text() == " 调整切图位置"
        assert not win.btn_adjust_cuts.isEnabled()
    finally:
        win.close()


def test_processed_view_compacts_drop_zone_and_keeps_preview_labels_visible(qapp, tmp_path):
    paths = []
    for index in range(3):
        path = tmp_path / f"slice_{index}.png"
        Image.new("RGB", (650, 300), "white").save(path)
        paths.append(str(path))

    win = MainWindow()
    try:
        win._on_processed(paths)
        assert win.drop_zone.maximumHeight() <= 80
        assert win.drop_zone.icon_label.isHidden()
        assert win.preview_area.height() >= 155
    finally:
        win.close()


def test_copy_html_does_not_delete_other_process_temp_files(qapp, tmp_path, monkeypatch):
    source = tmp_path / "slice.png"
    Image.new("RGB", (650, 300), "white").save(source)
    foreign = Path(tempfile.gettempdir()) / "mail_foreign_process.png"
    Image.new("RGB", (10, 10), "red").save(foreign)

    class FakeClipboard:
        def setMimeData(self, mime):
            self.mime = mime

    fake_clipboard = FakeClipboard()
    monkeypatch.setattr(QGuiApplication, "clipboard", lambda: fake_clipboard)

    win = MainWindow()
    try:
        win.slice_paths = [str(source)]
        win.slice_source_index = {source.name: 1.0}
        win._copy_html()
        assert foreign.exists()
    finally:
        foreign.unlink(missing_ok=True)
        win.close()
