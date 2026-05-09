"""
Outlook 长图无损插入工具 - 主程序 V3
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
    QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QFont, QFontMetrics, QKeyEvent, QGuiApplication, QImage

from image_slicer import detect_and_slice, get_image_info
from pdf_slicer import pdf_to_images
from ppt_slicer import pptx_to_images
from html_assembler import assemble_html
from outlook_sender import create_email_with_images


VERSION = "V3.0.20260511"


class Config:
    APP_TITLE = f"Outlook 长图助手 {VERSION}"
    DEFAULT_WIDTH = 960
    MAX_HEIGHT_PER_SLICE = 1728
    MAX_SLICE_COUNT = 20
    WINDOW_WIDTH = 720
    WINDOW_HEIGHT = 780
    SUPPORTED_EXTENSIONS = (
        ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif", ".pdf", ".pptx", ".ppt"
    )


class Theme:
    # Primary
    PRIMARY = "#0078D4"
    PRIMARY_HOVER = "#2563EB"
    PRIMARY_ACTIVE = "#1D4ED8"
    PRIMARY_DISABLED = "#BFDBFE"
    PRIMARY_TEXT = "#FFFFFF"
    # Secondary
    SECONDARY_BG = "#F3F4F6"
    SECONDARY_HOVER = "#E5E7EB"
    SECONDARY_BORDER = "#D1D5DB"
    SECONDARY_TEXT = "#374151"
    # Functional
    SUCCESS = "#10B981"
    SUCCESS_BG = "#ECFDF5"
    WARNING = "#F59E0B"
    ERROR = "#EF4444"
    ERROR_BG = "#FEF2F2"
    # Neutral
    BG = "#F8FAFC"
    CARD = "#FFFFFF"
    BORDER = "#E5E7EB"
    BORDER_HOVER = "#D1D5DB"
    BORDER_FOCUS = "#0078D4"
    # Text
    TEXT_PRIMARY = "#111827"
    TEXT_SECONDARY = "#6B7280"
    TEXT_PLACEHOLDER = "#9CA3AF"
    TEXT_DISABLED = "#D1D5DB"
    # DropZone
    DROPZONE_IDLE_BORDER = "#D1D5DB"
    DROPZONE_HOVER_BG = "#EFF6FF"
    DROPZONE_HOVER_BORDER = "#0078D4"


def _btn_metric(text: str, font_size: int = 13) -> QSize:
    """估算按钮所需最小尺寸（中文 + 英文通用）"""
    fm = QFontMetrics(QFont("Microsoft YaHei", font_size))
    w = fm.horizontalAdvance(text) + 36
    h = max(38, fm.height() + 16)
    return QSize(w, h)


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

        self.tip_label = QLabel("支持 JPG、PNG、WebP、GIF、PDF、PPT、PPTX")
        self.tip_label.setAlignment(Qt.AlignCenter)
        self.tip_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px;")

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.tip_label)

    def _apply_style(self):
        border = Theme.DROPZONE_HOVER_BORDER if self._hovered else Theme.DROPZONE_IDLE_BORDER
        background = Theme.DROPZONE_HOVER_BG if self._hovered else Theme.CARD
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
            QMessageBox.warning(self, "格式不支持", "请选择图片、PDF 或 PPT 文件。")


class ProcessWorker(QThread):
    progress = Signal(int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, file_path: str, width: int):
        super().__init__()
        self.file_path = file_path
        self.width = width

    def _convert_and_slice(self, converter_fn, prefix: str, progress_before: int, progress_after: int) -> List[str]:
        """PDF/PPT 通用转换+切片逻辑，消除重复代码"""
        images = converter_fn(self.file_path)
        self.progress.emit(progress_before)
        slice_paths = []
        temp_dir = tempfile.gettempdir()
        for index, image in enumerate(images):
            path = os.path.join(temp_dir, f"{prefix}_{index}.png")
            image.save(path)
            slice_paths.append(path)
        self.progress.emit(progress_after)
        # 对每页结果进行二次切片（高度超限时）
        final_slices = []
        for path in slice_paths:
            tiles = detect_and_slice(path, max_height=Config.MAX_HEIGHT_PER_SLICE)
            final_slices.extend(tiles)
        return final_slices

    def run(self):
        try:
            ext = Path(self.file_path).suffix.lower()
            self.progress.emit(15)
            if ext == ".pdf":
                slice_paths = self._convert_and_slice(
                    pdf_to_images, "pdf_page", 45, 75
                )
            elif ext in (".pptx", ".ppt"):
                slice_paths = self._convert_and_slice(
                    pptx_to_images, "ppt_page", 45, 75
                )
            else:
                slice_paths = detect_and_slice(
                    self.file_path, max_height=Config.MAX_HEIGHT_PER_SLICE
                )
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
        self.setMinimumSize(480, 640)
        self.resize(Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)
        self.setStyleSheet(f"background: {Theme.BG};")

        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(14)

        # Header
        header = QLabel("🎯 Outlook 长图无损插入")
        header.setFont(QFont("Microsoft YaHei", 18, QFont.Bold))
        header.setStyleSheet(f"color: {Theme.TEXT_PRIMARY};")
        layout.addWidget(header)

        # Drop zone
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._handle_file)
        self.drop_zone.clicked.connect(self._select_file)
        layout.addWidget(self.drop_zone)

        # Row 1: 选择文件
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        btn_select = QPushButton("📁 选择文件")
        btn_select.setFont(QFont("Microsoft YaHei", 13))
        btn_select.setCursor(Qt.PointingHandCursor)
        btn_select.setStyleSheet(self._btn_style(Theme.CARD, Theme.TEXT_PRIMARY))
        btn_select.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_select.setFixedSize(_btn_metric("📁 选择文件", 13))
        btn_select.clicked.connect(self._select_file)
        row1.addWidget(btn_select)

        row1.addStretch()
        layout.addLayout(row1)

        # Preview area
        self.preview_area = QScrollArea()
        self.preview_area.setWidgetResizable(True)
        self.preview_area.setFixedHeight(150)
        self.preview_area.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {Theme.BORDER}; "
            f"border-radius: 12px; background: {Theme.CARD}; }}"
        )
        self.thumb_container = QWidget()
        self.thumb_grid = QGridLayout(self.thumb_container)
        self.thumb_grid.setContentsMargins(10, 10, 10, 10)
        self.thumb_grid.setSpacing(8)
        self.preview_area.setWidget(self.thumb_container)
        self.preview_area.hide()
        layout.addWidget(self.preview_area)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ border: none; background: {Theme.BORDER}; "
            f"border-radius: 2px; }}"
            f"QProgressBar::chunk {{ background: {Theme.PRIMARY}; "
            f"border-radius: 2px; }}"
        )
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Status
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Microsoft YaHei", 12))
        layout.addWidget(self.status_label)

        # Bottom buttons: Primary (创建Outlook邮件) + Secondary (保存切图)
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self.btn_send = QPushButton("创建 Outlook 邮件")
        self.btn_send.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setEnabled(False)
        self.btn_send.setStyleSheet(
            f"QPushButton {{ background: {Theme.PRIMARY}; color: {Theme.PRIMARY_TEXT}; border: none; "
            f"border-radius: 12px; font-weight: bold; "
            f"font-family: Microsoft YaHei, sans-serif; }}"
            f"QPushButton:hover {{ background: {Theme.PRIMARY_HOVER}; }}"
            f"QPushButton:pressed {{ background: {Theme.PRIMARY_ACTIVE}; }}"
            f"QPushButton:disabled {{ background: {Theme.PRIMARY_DISABLED}; "
            f"color: {Theme.TEXT_PLACEHOLDER}; }}"
        )
        self.btn_send.clicked.connect(self._send_email)
        self.btn_send.setFixedHeight(48)
        self.btn_send.setFixedSize(_btn_metric("创建 Outlook 邮件", 14))
        bottom_row.addWidget(self.btn_send)

        self.btn_save = QPushButton("保存切图")
        self.btn_save.setFont(QFont("Microsoft YaHei", 13, QFont.Medium))
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setEnabled(False)
        self.btn_save.setStyleSheet(
            f"QPushButton {{ background: {Theme.SECONDARY_BG}; color: {Theme.SECONDARY_TEXT}; "
            f"border: 1px solid {Theme.SECONDARY_BORDER}; border-radius: 10px; "
            f"font-family: Microsoft YaHei, sans-serif; }}"
            f"QPushButton:hover {{ background: {Theme.SECONDARY_HOVER}; }}"
            f"QPushButton:disabled {{ background: {Theme.SECONDARY_BG}; "
            f"color: {Theme.TEXT_DISABLED}; border-color: {Theme.BORDER}; }}"
        )
        self.btn_save.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_save.setFixedSize(_btn_metric("保存切图", 13))
        self.btn_save.setFixedHeight(40)
        self.btn_save.clicked.connect(self._save_slices)
        bottom_row.addWidget(self.btn_save)

        layout.addLayout(bottom_row)

        # Version label
        version_row = QHBoxLayout()
        version_row.addStretch()
        ver_label = QLabel(VERSION)
        ver_label.setStyleSheet(f"color: {Theme.TEXT_PLACEHOLDER}; font-size: 11px;")
        ver_label.setFont(QFont("Microsoft YaHei", 11))
        version_row.addWidget(ver_label)
        layout.addLayout(version_row)

    def _btn_style(self, bg: str, color: str) -> str:
        hover = Theme.PRIMARY_HOVER if bg == Theme.PRIMARY else Theme.SECONDARY_HOVER
        border = "1px solid transparent" if bg == Theme.PRIMARY else f"1px solid {Theme.BORDER}"
        return (
            f"QPushButton {{ background: {bg}; color: {color}; border: {border}; "
            f"border-radius: 10px; font-family: Microsoft YaHei, sans-serif; }}"
            f"QPushButton:hover {{ background: {hover}; }}"
            f"QPushButton:disabled {{ background: {Theme.SECONDARY_BG}; "
            f"color: {Theme.TEXT_DISABLED}; border-color: {Theme.BORDER}; }}"
        )

    def _set_status(self, text: str, level: str = "info"):
        """统一设置状态标签文字和样式，消除重复"""
        color_map = {
            "info": Theme.TEXT_SECONDARY,
            "success": Theme.SUCCESS,
            "error": Theme.ERROR,
            "warning": Theme.WARNING,
        }
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color_map.get(level, Theme.TEXT_SECONDARY)}; font-size: 12px;"
        )

    def keyPressEvent(self, event: QKeyEvent):
        """处理快捷键：Ctrl+O 打开文件，Ctrl+V 粘贴图片，Esc 重置"""
        modifiers = event.modifiers()
        if (modifiers & Qt.ControlModifier) and event.key() == Qt.Key_O:
            self._select_file()
        elif (modifiers & Qt.ControlModifier) and event.key() == Qt.Key_V:
            self._paste_image()
        elif event.key() == Qt.Key_Escape:
            self.reset_app()
        else:
            super().keyPressEvent(event)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片、PDF 或 PPT", "",
            "图片 (*.jpg *.jpeg *.png *.bmp *.webp *.gif);;PDF (*.pdf);;PPT/PPTX (*.pptx *.ppt)"
        )
        if path:
            self._handle_file(path)

    def _paste_image(self):
        """从剪贴板粘贴图片"""
        clipboard = QGuiApplication.clipboard()
        image = clipboard.image()
        if image is None or image.isNull():
            QMessageBox.warning(self, "粘贴失败", "剪贴板中没有图片内容。")
            return
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"paste_{os.getpid()}.png")
        image.save(temp_path)
        self._handle_file(temp_path)

    def _handle_file(self, path: str):
        """统一的文件处理入口（含切片数 > 20 确认逻辑）"""
        ext = Path(path).suffix.lower()

        # 图片文件：先估算切片数量，必要时弹确认框
        if ext not in (".pdf", ".pptx", ".ppt"):
            try:
                info = get_image_info(path)
                orig_h = info["height"]
                slice_count = (orig_h + Config.MAX_HEIGHT_PER_SLICE - 1) // Config.MAX_HEIGHT_PER_SLICE
                slice_count = max(1, slice_count)
                self.drop_zone.title_label.setText(Path(path).name)
                self.drop_zone.icon_label.setText("✅")
                self.drop_zone.tip_label.setText(f"预计生成 {slice_count} 张切片")

                if slice_count > Config.MAX_SLICE_COUNT:
                    reply = QMessageBox.warning(
                        self,
                        "切片数量较多",
                        f"当前图片预计将生成 <b>{slice_count}</b> 张切片（> {Config.MAX_SLICE_COUNT}），"
                        "是否继续处理？",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if reply != QMessageBox.Yes:
                        self.drop_zone.title_label.setText("拖拽或点击上传图片 / PDF")
                        self.drop_zone.icon_label.setText("📂")
                        self.drop_zone.tip_label.setText("支持 JPG、PNG、WebP、GIF、PDF、PPT、PPTX")
                        return
            except Exception as exc:
                QMessageBox.critical(self, "处理失败", str(exc))
                return

        self.file_path = path
        self.drop_zone.title_label.setText(Path(path).name)
        self.drop_zone.icon_label.setText("✅")
        self.drop_zone.tip_label.setText("正在处理...")
        self._set_status("正在处理，请稍候...", "info")
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self._start_worker(path)

    def _start_worker(self, path: str):
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        self.worker = ProcessWorker(path, Config.DEFAULT_WIDTH)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_processed)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_processed(self, paths: List[str]):
        self.slice_paths = paths
        self.progress_bar.hide()
        self.btn_send.setEnabled(bool(paths))
        self.btn_save.setEnabled(bool(paths))
        self._set_status(f"已生成 {len(paths)} 张切片，准备发送", "success")
        self._show_thumbnails(paths)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def _on_error(self, msg: str):
        self.progress_bar.hide()
        self._set_status(f"处理失败: {msg}", "error")
        QMessageBox.critical(self, "处理失败", msg)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

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
            thumb.setScaledContents(True)
            thumb.setStyleSheet(
                f"background: {Theme.CARD}; border-radius: 8px; "
                f"border: 1px solid {Theme.BORDER};"
            )
            pixmap = QPixmap(path).scaled(
                120, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            thumb.setPixmap(pixmap)
            self.thumb_grid.addWidget(thumb, row, col)

        self.preview_area.show()

    def _save_slices(self):
        if not self.slice_paths:
            return
        save_dir = QFileDialog.getExistingDirectory(
            self, "选择保存文件夹", ""
        )
        if not save_dir:
            return
        try:
            import shutil as shutil_module
            for path in self.slice_paths:
                fname = os.path.basename(path)
                dst = os.path.join(save_dir, fname)
                shutil_module.copy2(path, dst)
            QMessageBox.information(
                self, "保存成功", f"已保存 {len(self.slice_paths)} 张切片到：\n{save_dir}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def _send_email(self):
        if not self.slice_paths:
            return
        try:
            html_content = assemble_html(self.slice_paths, Config.DEFAULT_WIDTH)
            create_email_with_images(
                html_content,
                subject="长图邮件",
                to="",
                image_paths=self.slice_paths
            )
            self._set_status("✅ 邮件窗口已打开，请检查后发送", "success")
        except Exception as exc:
            QMessageBox.critical(self, "发送失败", str(exc))

    def reset_app(self):
        self.slice_paths = []
        self.file_path = None
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        self.drop_zone.title_label.setText("拖拽或点击上传图片 / PDF")
        self.drop_zone.icon_label.setText("📂")
        self.drop_zone.tip_label.setText("支持 JPG、PNG、WebP、GIF、PDF、PPT、PPTX")
        self.preview_area.hide()
        self.btn_send.setEnabled(False)
        self.btn_save.setEnabled(False)
        self._set_status("")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 12))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
