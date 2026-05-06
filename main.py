"""
Outlook 长图无损插入工具 - 主程序
PySide6 窗口应用，支持拖拽上传、自动切片及 Outlook 自动化发送
"""
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QProgressBar, QMessageBox, QFileDialog,
    QFrame, QGridLayout, QScrollArea,
    QLineEdit, QSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QFont

from image_slicer import detect_and_slice
from pdf_slicer import pdf_to_images
from html_assembler import assemble_html
from outlook_sender import create_email_with_images


class Config:
    APP_TITLE = "Outlook 长图助手"
    DEFAULT_WIDTH = 650
    MAX_HEIGHT_PER_SLICE = 1200
    WINDOW_WIDTH = 680
    WINDOW_HEIGHT = 720
    SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif", ".pdf")


class Theme:
    PRIMARY = "#0078D4"
    PRIMARY_HOVER = "#2563EB"
    BG = "#F8FAFC"
    CARD = "#FFFFFF"
    BORDER = "#E5E7EB"
    TEXT = "#111827"
    SUBTEXT = "#6B7280"
    TEXT_SECONDARY = "#6B7280"
    SUCCESS = "#10B981"
    ERROR = "#EF4444"


class DropZone(QFrame):
    file_dropped = Signal(str)
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self._hovered = False
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 30, 28, 30)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel("📂")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 46px;")

        self.title_label = QLabel("拖拽或点击上传图片 / PDF")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))

        self.tip_label = QLabel("支持 JPG、PNG、WebP、GIF、PDF")
        self.tip_label.setAlignment(Qt.AlignCenter)
        self.tip_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.tip_label)

    def _apply_style(self):
        border = Theme.PRIMARY if self._hovered else Theme.BORDER
        background = "#EFF6FF" if self._hovered else Theme.CARD
        self.setStyleSheet(
            f"QFrame {{ background: {background}; border: 2px dashed {border}; border-radius: 16px; }}"
        )

    def enterEvent(self, event):
        self._hovered = True
        self._apply_style()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._apply_style()
        super().leaveEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._hovered = True
            self._apply_style()
            self.title_label.setText("松开以上传文件")

    def dragLeaveEvent(self, event):
        self._hovered = False
        self._apply_style()
        self.title_label.setText("拖拽或点击上传图片 / PDF")

    def dropEvent(self, event: QDropEvent):
        self._hovered = False
        self._apply_style()
        if urls := event.mimeData().urls():
            path = urls[0].toLocalFile()
            self._submit(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _submit(self, path: str):
        if Path(path).suffix.lower() in Config.SUPPORTED_EXTENSIONS:
            self.file_dropped.emit(path)
        else:
            QMessageBox.warning(self, "格式不支持", "请选择图片或 PDF 文件。")


class ProcessWorker(QThread):
    progress = Signal(int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, file_path: str, width: int):
        super().__init__()
        self.file_path = file_path
        self.width = width

    def run(self):
        try:
            ext = Path(self.file_path).suffix.lower()
            self.progress.emit(15)
            if ext == ".pdf":
                images = pdf_to_images(self.file_path)
                self.progress.emit(45)
                slice_paths = []
                temp_dir = tempfile.gettempdir()
                for index, image in enumerate(images):
                    path = os.path.join(temp_dir, f"pdf_page_{index}.png")
                    image.save(path)
                    slice_paths.append(path)
            else:
                slice_paths = detect_and_slice(self.file_path, max_height=Config.MAX_HEIGHT_PER_SLICE)
            self.progress.emit(100)
            self.finished.emit(slice_paths)
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.slice_paths: List[str] = []
        self.file_path: Optional[str] = None
        self.worker: Optional[ProcessWorker] = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle(Config.APP_TITLE)
        self.setFixedSize(Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
        self.setStyleSheet(f"background: {Theme.BG};")

        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        header = QLabel("Outlook 长图无损插入")
        header.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        header.setStyleSheet(f"color: {Theme.TEXT};")
        layout.addWidget(header)

        subtitle = QLabel("自动识别图片/PDF，生成切片并打开 Outlook 邮件窗口。")
        subtitle.setStyleSheet(f"color: {Theme.SUBTEXT}; font-size: 12px;")
        layout.addWidget(subtitle)

        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self.handle_file_selection)
        self.drop_zone.clicked.connect(self._select_file)
        layout.addWidget(self.drop_zone)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)
        self.btn_select = QPushButton("选择文件")
        self.btn_select.setFixedHeight(42)
        self.btn_select.setStyleSheet(self._btn_style(Theme.CARD, Theme.TEXT))
        self.btn_select.clicked.connect(self._select_file)

        self.btn_reset = QPushButton("重置")
        self.btn_reset.setFixedHeight(42)
        self.btn_reset.setStyleSheet(self._btn_style(Theme.CARD, Theme.SUBTEXT))
        self.btn_reset.clicked.connect(self.reset_app)

        buttons_row.addWidget(self.btn_select)
        buttons_row.addWidget(self.btn_reset)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        self.input_to = QLineEdit()
        self.input_to.setPlaceholderText("收件人邮箱（可选）")
        self.input_subject = QLineEdit()
        self.input_subject.setPlaceholderText("邮件标题（可选）")
        for widget in (self.input_to, self.input_subject):
            widget.setFixedHeight(36)
            widget.setStyleSheet(self._input_style())
            layout.addWidget(widget)

        width_row = QHBoxLayout()
        width_label = QLabel("显示宽度")
        width_label.setStyleSheet(f"color: {Theme.SUBTEXT};")
        self.spin_width = QSpinBox()
        self.spin_width.setRange(300, 1200)
        self.spin_width.setValue(Config.DEFAULT_WIDTH)
        self.spin_width.setSuffix(" px")
        self.spin_width.setFixedWidth(110)
        self.spin_width.setFixedHeight(36)
        self.spin_width.setStyleSheet(self._input_style())
        width_row.addWidget(width_label)
        width_row.addWidget(self.spin_width)
        width_row.addStretch()
        layout.addLayout(width_row)

        self.preview_area = QScrollArea()
        self.preview_area.setWidgetResizable(True)
        self.preview_area.setFixedHeight(150)
        self.preview_area.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {Theme.BORDER}; border-radius: 12px; background: {Theme.CARD}; }}"
        )
        self.thumb_container = QWidget()
        self.thumb_grid = QGridLayout(self.thumb_container)
        self.thumb_grid.setContentsMargins(10, 10, 10, 10)
        self.thumb_grid.setSpacing(8)
        self.preview_area.setWidget(self.thumb_container)
        self.preview_area.hide()
        layout.addWidget(self.preview_area)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ border: none; background: {Theme.BORDER}; border-radius: 2px; }}"
            f"QProgressBar::chunk {{ background: {Theme.PRIMARY}; border-radius: 2px; }}"
        )
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {Theme.SUBTEXT}; font-size: 12px;")
        layout.addWidget(self.status_label)

        self.btn_send = QPushButton("创建 Outlook 邮件")
        self.btn_send.setFixedHeight(46)
        self.btn_send.setEnabled(False)
        self.btn_send.setStyleSheet(self._btn_style(Theme.PRIMARY, "white", bold=True))
        self.btn_send.clicked.connect(self._send_email)
        layout.addWidget(self.btn_send)

    def _input_style(self) -> str:
        return (
            f"QLineEdit, QSpinBox {{"
            f"border: 1px solid {Theme.BORDER};"
            f"border-radius: 8px;"
            f"padding: 0 10px;"
            f"background: {Theme.CARD};"
            f"color: {Theme.TEXT};"
            f"}}"
            f"QLineEdit:focus, QSpinBox:focus {{ border-color: {Theme.PRIMARY}; }}"
        )

    def _btn_style(self, bg: str, color: str, bold: bool = False) -> str:
        weight = "bold" if bold else "normal"
        hover = Theme.PRIMARY_HOVER if bg == Theme.PRIMARY else "#F3F4F6"
        border = "1px solid transparent" if bg == Theme.PRIMARY else f"1px solid {Theme.BORDER}"
        return (
            f"QPushButton {{ background: {bg}; color: {color}; border: {border}; border-radius: 10px;"
            f"font-weight: {weight}; font-size: 14px; }}"
            f"QPushButton:hover {{ background: {hover}; }}"
            f"QPushButton:disabled {{ background: {Theme.BORDER}; color: {Theme.SUBTEXT}; }}"
        )

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片或 PDF", "",
            "图片 (*.jpg *.jpeg *.png *.bmp *.webp *.gif);;PDF (*.pdf)"
        )
        if path:
            self.handle_file_selection(path)

    def handle_file_selection(self, path: str):
        self.file_path = path
        self.drop_zone.title_label.setText(Path(path).name)
        self.drop_zone.icon_label.setText("✅")
        self.drop_zone.tip_label.setText("已选择文件，可继续切片")
        self.status_label.setText("正在处理，请稍候...")
        self.status_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")
        self.progress_bar.setValue(0)
        self.progress_bar.show()

        self.worker = ProcessWorker(path, self.spin_width.value())
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_processed)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_processed(self, paths: List[str]):
        self.slice_paths = paths
        self.progress_bar.hide()
        self.btn_send.setEnabled(bool(paths))
        self.status_label.setText(f"已生成 {len(paths)} 张切片，准备发送")
        self.status_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 12px;")
        self._show_thumbnails(paths)

    def _on_error(self, msg: str):
        self.progress_bar.hide()
        self.status_label.setText(f"处理失败: {msg}")
        self.status_label.setStyleSheet(f"color: {Theme.ERROR}; font-size: 12px;")
        QMessageBox.critical(self, "处理失败", msg)

    def _show_thumbnails(self, paths: List[str]):
        while self.thumb_grid.count():
            item = self.thumb_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 4
        for i, path in enumerate(paths):
            row, col = divmod(i, cols)
            thumb = QLabel()
            thumb.setFixedSize(120, 100)
            thumb.setStyleSheet(f"background: {Theme.CARD}; border-radius: 8px;")
            pixmap = QPixmap(path).scaled(120, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            thumb.setPixmap(pixmap)
            self.thumb_grid.addWidget(thumb, row, col)

        self.preview_area.show()

    def _send_email(self):
        if not self.slice_paths:
            return
        subject = self.input_subject.text().strip() or "长图邮件"
        to_addr = self.input_to.text().strip()
        width = self.spin_width.value()
        try:
            html_content = assemble_html(self.slice_paths, width)
            create_email_with_images(html_content, subject, to_addr)
            self.status_label.setText("✅ 邮件窗口已打开，请检查后发送")
            self.status_label.setStyleSheet(f"color: {Theme.SUCCESS}; font-size: 12px;")
        except Exception as exc:
            QMessageBox.critical(self, "发送失败", str(exc))

    def reset_app(self):
        self.slice_paths = []
        self.file_path = None
        self.drop_zone.title_label.setText("拖拽或点击上传图片 / PDF")
        self.drop_zone.icon_label.setText("📂")
        self.drop_zone.tip_label.setText("支持 JPG、PNG、WebP、GIF、PDF")
        self.preview_area.hide()
        self.btn_send.setEnabled(False)
        self.status_label.setText("")
        self.input_to.clear()
        self.input_subject.clear()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
