import pytest
from PIL import Image
import tempfile
from pathlib import Path

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QGuiApplication

from main import MainWindow


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_classic_outlook_defaults_are_clear(qapp):
    win = MainWindow()
    try:
        assert win.edit_width.text() == "960"
        assert win.chk_smart.text() == "避开文字切图（推荐）"
        assert win.btn_send.text() == "在 Outlook 中创建邮件"
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
        assert win.btn_adjust_cuts.text() == "调整切图位置"
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
        assert win.drop_zone.tip_label.isHidden()
        assert win.drop_zone.title_label.text() == "处理完成；可重新拖入文件替换"
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


def test_windows_copy_uses_native_cf_html_writer(qapp, tmp_path, monkeypatch):
    source = tmp_path / "slice.png"
    Image.new("RGB", (648, 120), "white").save(source)
    captured = []
    monkeypatch.setattr("main.sys.platform", "win32")
    monkeypatch.setattr("main.copy_cf_html_to_clipboard", captured.append)

    win = MainWindow()
    try:
        win.slice_paths = [str(source)]
        win.slice_source_index = {source.name: 1.0}
        win._copy_html()

        assert len(captured) == 1
        assert captured[0].startswith(b"Version:0.9")
    finally:
        win.close()


def test_window_resize_scales_text_buttons_icons_and_corner_radius(qapp):
    win = MainWindow()
    try:
        win.show()
        win.resize(760, 720)
        qapp.processEvents()
        base_font = win.btn_send.font().pointSizeF()
        base_height = win.btn_send.minimumHeight()
        base_icon = win.btn_send.iconSize().width()

        win.resize(1100, 900)
        qapp.processEvents()

        assert win.btn_send.font().pointSizeF() > base_font
        assert win.btn_send.minimumHeight() > base_height
        assert win.btn_send.iconSize().width() > base_icon
        assert "border-radius: 28px" in win.btn_send.styleSheet()
        assert "padding:" in win.btn_send.styleSheet()
    finally:
        win.close()


def test_fonts_request_antialiasing(qapp):
    win = MainWindow()
    try:
        strategy = win.header_title.font().styleStrategy()
        assert strategy & QFont.StyleStrategy.PreferAntialias
    finally:
        win.close()


def test_resize_preserves_runtime_status_color(qapp):
    win = MainWindow()
    try:
        win.show()
        win._set_status("处理失败", "error")
        win.resize(1100, 900)
        qapp.processEvents()

        assert "#ef4444" in win.status_label.styleSheet()
        assert "处理失败" in win.status_label.text()
    finally:
        win.close()


def test_processed_thumbnails_follow_global_scale(qapp, tmp_path):
    paths = []
    for index in range(6):
        path = tmp_path / f"thumb_{index}.png"
        Image.new("RGB", (648, 120), "white").save(path)
        paths.append(str(path))

    win = MainWindow()
    try:
        win.show()
        win.resize(760, 720)
        qapp.processEvents()
        win._on_processed(paths)
        qapp.processEvents()
        base_width = win.thumb_grid.itemAt(0).widget().width()

        win.resize(1100, 900)
        qapp.processEvents()

        assert win.thumb_grid.itemAt(0).widget().width() > base_width
        assert win.thumb_grid.itemAtPosition(0, 4) is not None
    finally:
        win.close()


def test_export_progress_is_visible_while_rendering(qapp, tmp_path, monkeypatch):
    source = tmp_path / "source.png"
    Image.new("RGB", (320, 240), "white").save(source)

    def fake_render(path):
        return [Image.open(path).convert("RGB")]

    monkeypatch.setattr("main._render_source_to_images", fake_render)
    monkeypatch.setattr("main.QMessageBox.information", lambda *args, **kwargs: None)

    win = MainWindow()
    try:
        win._export_images([str(source)], save_dir=str(tmp_path), fmt="png", keep_alpha=True)
        observed = (win.progress_bar.isHidden(), win.progress_bar.value())
        while win._export_worker is not None and win._export_worker.isRunning():
            qapp.processEvents()
        qapp.processEvents()
        assert observed[0] is False
        assert observed[1] > 0
        assert (tmp_path / "source.png").exists()
    finally:
        win.close()


def test_export_runs_rendering_off_the_gui_thread(qapp, tmp_path, monkeypatch):
    import threading

    source = tmp_path / "threaded.png"
    Image.new("RGB", (64, 64), "white").save(source)
    render_threads = []

    def fake_render(path):
        render_threads.append(threading.current_thread())
        return [Image.open(path).convert("RGB")]

    monkeypatch.setattr("main._render_source_to_images", fake_render)
    monkeypatch.setattr("main.QMessageBox.information", lambda *args, **kwargs: None)

    win = MainWindow()
    try:
        win._export_images([str(source)], save_dir=str(tmp_path), fmt="png", keep_alpha=True)
        assert win._export_worker is not None
        while win._export_worker is not None and win._export_worker.isRunning():
            qapp.processEvents()
        qapp.processEvents()

        assert render_threads
        assert render_threads[0] is not threading.main_thread()
    finally:
        win.close()
