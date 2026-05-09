"""
Outlook 长图无损插入工具 - 主程序 V3
PySide6 窗口应用，支持拖拽上传、自动切片及 Outlook 自动化发送
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QProgressBar, QMessageBox, QFileDialog,
    QFrame, QGridLayout, QScrollArea,
    QSizePolicy, QLineEdit, QSpinBox,
    QPlainTextEdit
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QFont, QFontMetrics, QKeyEvent, QGuiApplication

from image_slicer import detect_and_slice, get_image_info
from pdf_slicer import pdf_to_images
from ppt_slicer import pptx_to_images
from html_assembler import assemble_html
from outlook_sender import create_email_with_images


VERSION = "V3.0.20260512"


# ────────────────────────────────────────────
# 配置 & 主题
# ────────────────────────────────────────────

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
    # Secondary (辅助按钮)
    SECONDARY_BG = "#FFFFFF"
    SECONDARY_HOVER = "#F3F4F6"
    SECONDARY_BORDER = "#D1D5DB"
    SECONDARY_TEXT = "#374151"
    # Ghost (工具类操作)
    GHOST_BG = "#F3F4F6"
    GHOST_HOVER = "#E5E7EB"
    GHOST_TEXT = "#374151"
    # Functional
    SUCCESS = "#10B981"
    ERROR = "#EF4444"
    WARNING = "#F59E0B"
    # Surface
    BG = "#F0F2F5"
    CARD = "#FFFFFF"
    BORDER = "#E4E7EC"
    BORDER_HOVER = "#C8CDD6"
    BORDER_FOCUS = "#0078D4"
    # Text
    TEXT_PRIMARY = "#111827"
    TEXT_SECONDARY = "#6B7280"
    TEXT_PLACEHOLDER = "#9CA3AF"
    TEXT_DISABLED = "#C8CDD6"
    # DropZone
    DROPZONE_IDLE_BORDER = "#D1D5DB"
    DROPZONE_HOVER_BG = "#EFF6FF"
    DROPZONE_HOVER_BORDER = "#0078D4"
    # Section separator
    SEPARATOR = "#F0F2F5"


def _font(family: str = "Microsoft YaHei", size: int = 12, weight: int = QFont.Normal) -> QFont:
    return QFont(family, size, weight)


def _btn_size(text: str, font_size: int = 13, extra_w: int = 36, height: int = 38) -> QSize:
    fm = QFontMetrics(QFont("Microsoft YaHei", font_size))
    return QSize(fm.horizontalAdvance(text) + extra_w, height)


# ────────────────────────────────────────────
# 组件样式字符串（集中管理）
# ────────────────────────────────────────────

def _btn_primary() -> str:
    return (
        f"QPushButton {{ background: {Theme.PRIMARY}; color: {Theme.PRIMARY_TEXT}; "
        f"border: none; border-radius: 10px; font-family: Microsoft YaHei, sans-serif; }}"
        f"QPushButton:hover {{ background: {Theme.PRIMARY_HOVER}; }}"
        f"QPushButton:pressed {{ background: {Theme.PRIMARY_ACTIVE}; }}"
        f"QPushButton:disabled {{ background: {Theme.PRIMARY_DISABLED}; color: {Theme.TEXT_PLACEHOLDER}; }}"
    )


def _btn_secondary() -> str:
    return (
        f"QPushButton {{ background: {Theme.SECONDARY_BG}; color: {Theme.SECONDARY_TEXT}; "
        f"border: 1px solid {Theme.SECONDARY_BORDER}; border-radius: 10px; "
        f"font-family: Microsoft YaHei, sans-serif; }}"
        f"QPushButton:hover {{ background: {Theme.SECONDARY_HOVER}; border-color: {Theme.BORDER_HOVER}; }}"
        f"QPushButton:disabled {{ color: {Theme.TEXT_DISABLED}; border-color: {Theme.BORDER}; }}"
    )


def _btn_ghost() -> str:
    return (
        f"QPushButton {{ background: {Theme.GHOST_BG}; color: {Theme.GHOST_TEXT}; "
        f"border: 1px solid {Theme.SECONDARY_BORDER}; border-radius: 8px; "
        f"font-family: Microsoft YaHei, sans-serif; }}"
        f"QPushButton:hover {{ background: {Theme.GHOST_HOVER}; }}"
        f"QPushButton:disabled {{ color: {Theme.TEXT_DISABLED}; }}"
    )


def _input_style() -> str:
    return (
        f"QLineEdit, QSpinBox {{ background: {Theme.CARD}; color: {Theme.TEXT_PRIMARY}; "
        f"border: 1px solid {Theme.BORDER}; border-radius: 8px; "
        f"padding: 0 12px; font-family: Microsoft YaHei, sans-serif; }}"
        f"QLineEdit:focus, QSpinBox:focus {{ border-color: {Theme.BORDER_FOCUS}; }}"
        f"QLineEdit::placeholder {{ color: {Theme.TEXT_PLACEHOLDER}; }}"
    )


# ────────────────────────────────────────────
# 拖放区域
# ────────────────────────────────────────────

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
        layout.setContentsMargins(28, 32, 28, 32)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel("📂")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 44px; background: transparent; border: none;")

        self.title_label = QLabel("拖拽图片到此处")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(_font("Microsoft YaHei", 14, QFont.Bold))
        self.title_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;")

        self.tip_label = QLabel("支持 JPG · PNG · PDF · PPT，点击上传")
        self.tip_label.setAlignment(Qt.AlignCenter)
        self.tip_label.setFont(_font("Microsoft YaHei", 12))
        self.tip_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent; border: none;")

        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.tip_label)

    def _apply_style(self):
        border = Theme.DROPZONE_HOVER_BORDER if self._hovered else Theme.DROPZONE_IDLE_BORDER
        bg = Theme.DROPZONE_HOVER_BG if self._hovered else Theme.CARD
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 2px dashed {border}; "
            f"border-radius: 14px; }}"
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
            self.title_label.setText("松开以上传")

    def dragLeaveEvent(self, event):
        self._hovered = False
        self._apply_style()
        self.title_label.setText("拖拽图片到此处")

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


# ────────────────────────────────────────────
# 后台处理线程
# ────────────────────────────────────────────

class ProcessWorker(QThread):
    progress = Signal(int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, file_path: str, width: int):
        super().__init__()
        self.file_path = file_path
        self.width = width

    def _convert_and_slice(self, converter_fn, prefix: str, p_before: int, p_after: int) -> List[str]:
        """PDF/PPT 通用转换 + 切片，消除重复代码"""
        images = converter_fn(self.file_path)
        self.progress.emit(p_before)
        temp_dir = tempfile.gettempdir()
        slice_paths = []
        for index, image in enumerate(images):
            path = os.path.join(temp_dir, f"{prefix}_{index}.png")
            image.save(path)
            slice_paths.append(path)
        self.progress.emit(p_after)
        # 每页结果若高度超限则二次切片
        final = []
        for p in slice_paths:
            final.extend(detect_and_slice(p, max_height=Config.MAX_HEIGHT_PER_SLICE))
        return final

    def run(self):
        try:
            ext = Path(self.file_path).suffix.lower()
            self.progress.emit(15)
            if ext == ".pdf":
                slice_paths = self._convert_and_slice(pdf_to_images, "pdf_page", 45, 75)
            elif ext in (".pptx", ".ppt"):
                slice_paths = self._convert_and_slice(pptx_to_images, "ppt_page", 45, 75)
            else:
                slice_paths = detect_and_slice(self.file_path, max_height=Config.MAX_HEIGHT_PER_SLICE)
            self.progress.emit(100)
            self.finished.emit(slice_paths)
        except Exception as exc:
            self.error.emit(str(exc))


# ────────────────────────────────────────────
# 主窗口
# ────────────────────────────────────────────

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

        container = QWidget()
        self.setCentralWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        # ══ Header ══════════════════════════════
        title = QLabel("Outlook 长图无损插入")
        title.setFont(_font("Microsoft YaHei", 20, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        root.addWidget(title)

        subtitle = QLabel("自动识别图片/PDF/PPT，切片后插入邮件正文，保持原始清晰度")
        subtitle.setFont(_font("Microsoft YaHei", 12))
        subtitle.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        root.addWidget(subtitle)

        # ══ Drop Zone ════════════════════════════
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._handle_file)
        self.drop_zone.clicked.connect(self._select_file)
        root.addWidget(self.drop_zone)

        # ══ 工具栏（重置 + 宽度） ══════════════
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.btn_reset = QPushButton("🔄 重置")
        self.btn_reset.setFont(_font("Microsoft YaHei", 12))
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet(_btn_ghost())
        self.btn_reset.setFixedSize(_btn_size("🔄 重置", 12, extra_w=20, height=34))
        self.btn_reset.clicked.connect(self.reset_app)
        toolbar.addWidget(self.btn_reset)

        width_lbl = QLabel("显示宽度")
        width_lbl.setFont(_font("Microsoft YaHei", 12))
        width_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        toolbar.addWidget(width_lbl)

        self.spin_width = QSpinBox()
        self.spin_width.setFont(_font("Microsoft YaHei", 12))
        self.spin_width.setRange(400, 1920)
        self.spin_width.setValue(Config.DEFAULT_WIDTH)
        self.spin_width.setSuffix(" px")
        self.spin_width.setFixedSize(100, 34)
        self.spin_width.setStyleSheet(
            f"QSpinBox {{ background: {Theme.CARD}; color: {Theme.TEXT_PRIMARY}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 8px; "
            f"padding: 0 8px; font-family: Microsoft YaHei, sans-serif; }}"
            f"QSpinBox:focus {{ border-color: {Theme.BORDER_FOCUS}; }}"
        )
        toolbar.addWidget(self.spin_width)
        toolbar.addStretch()

        root.addLayout(toolbar)

        # ══ 邮件标题 ════════════════════════════
        subject_lbl = QLabel("邮件标题（可选）")
        subject_lbl.setFont(_font("Microsoft YaHei", 12))
        subject_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        root.addWidget(subject_lbl)

        self.input_subject = QLineEdit()
        self.input_subject.setFont(_font("Microsoft YaHei", 13))
        self.input_subject.setPlaceholderText("在此输入邮件标题，留空则使用默认标题")
        self.input_subject.setFixedHeight(40)
        self.input_subject.setStyleSheet(_input_style())
        root.addWidget(self.input_subject)

        # ══ 预览区 ═════════════════════════════
        self.preview_area = QScrollArea()
        self.preview_area.setWidgetResizable(True)
        self.preview_area.setFixedHeight(140)
        self.preview_area.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {Theme.BORDER}; border-radius: 12px; "
            f"background: {Theme.CARD}; }}"
        )
        self.thumb_container = QWidget()
        self.thumb_grid = QGridLayout(self.thumb_container)
        self.thumb_grid.setContentsMargins(10, 10, 10, 10)
        self.thumb_grid.setSpacing(8)
        self.preview_area.setWidget(self.thumb_container)
        self.preview_area.hide()
        root.addWidget(self.preview_area)

        # ══ 进度条 ══════════════════════════════
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ border: none; background: {Theme.BORDER}; border-radius: 2px; }}"
            f"QProgressBar::chunk {{ background: {Theme.PRIMARY}; border-radius: 2px; }}"
        )
        self.progress_bar.hide()
        root.addWidget(self.progress_bar)

        # ══ 状态 ═══════════════════════════════
        self.status_label = QLabel("")
        self.status_label.setFont(_font("Microsoft YaHei", 12))
        self.status_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        root.addWidget(self.status_label)

        # ══ 底部按钮区（一行并排，主次分明） ═══════
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.setContentsMargins(0, 4, 0, 0)

        self.btn_send = QPushButton("创建 Outlook 邮件")
        self.btn_send.setFont(_font("Microsoft YaHei", 14, QFont.Bold))
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setEnabled(False)
        self.btn_send.setStyleSheet(_btn_primary())
        self.btn_send.setFixedHeight(44)
        self.btn_send.setMinimumSize(_btn_size("创建 Outlook 邮件", 14, extra_w=48, height=44))
        self.btn_send.clicked.connect(self._send_email)

        self.btn_save = QPushButton("保存切图到本地")
        self.btn_save.setFont(_font("Microsoft YaHei", 13, QFont.Medium))
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setEnabled(False)
        self.btn_save.setStyleSheet(_btn_secondary())
        self.btn_save.setFixedHeight(44)
        self.btn_save.setMinimumSize(_btn_size("保存切图到本地", 13, extra_w=36, height=44))
        self.btn_save.clicked.connect(self._save_slices)

        btn_row.addWidget(self.btn_send, stretch=5)
        btn_row.addWidget(self.btn_save, stretch=5)
        root.addLayout(btn_row)

        # ══ 版本 ════════════════════════════════
        ver_row = QHBoxLayout()
        ver_row.addStretch()
        ver_lbl = QLabel(f"v{VERSION}")
        ver_lbl.setFont(_font("Microsoft YaHei", 11))
        ver_lbl.setStyleSheet(f"color: {Theme.TEXT_PLACEHOLDER}; background: transparent;")
        ver_row.addWidget(ver_lbl)
        root.addLayout(ver_row)

    # ── 状态统一设置 ──────────────────────────
    def _set_status(self, text: str, level: str = "info"):
        colors = {
            "info": Theme.TEXT_SECONDARY,
            "success": Theme.SUCCESS,
            "error": Theme.ERROR,
            "warning": Theme.WARNING,
        }
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {colors.get(level, Theme.TEXT_SECONDARY)}; "
            f"font-size: 12px; background: transparent;"
        )

    # ── 快捷键 ────────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        mod = event.modifiers()
        if (mod & Qt.ControlModifier) and event.key() == Qt.Key_O:
            self._select_file()
        elif (mod & Qt.ControlModifier) and event.key() == Qt.Key_V:
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
        image = QGuiApplication.clipboard().image()
        if image is None or image.isNull():
            QMessageBox.warning(self, "粘贴失败", "剪贴板中没有图片内容。")
            return
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"paste_{os.getpid()}.png")
        image.save(temp_path)
        self._handle_file(temp_path)

    def _handle_file(self, path: str):
        ext = Path(path).suffix.lower()
        self.file_path = path
        self.drop_zone.title_label.setText(Path(path).name)
        self.drop_zone.icon_label.setText("✅")
        self.drop_zone.tip_label.setText("正在处理...")

        # 图片文件先估算切片数量
        if ext not in (".pdf", ".pptx", ".ppt"):
            try:
                info = get_image_info(path)
                orig_h = info["height"]
                sc = (orig_h + Config.MAX_HEIGHT_PER_SLICE - 1) // Config.MAX_HEIGHT_PER_SLICE
                sc = max(1, sc)
                self.drop_zone.tip_label.setText(f"预计生成 {sc} 张切片")

                if sc > Config.MAX_SLICE_COUNT:
                    reply = QMessageBox.warning(
                        self, "切片数量较多",
                        f"当前图片预计生成 <b>{sc}</b> 张切片（> {Config.MAX_SLICE_COUNT}），是否继续？",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                    )
                    if reply != QMessageBox.Yes:
                        self._reset_drop_zone()
                        return
            except Exception as exc:
                QMessageBox.critical(self, "处理失败", str(exc))
                return

        self._set_status("正在处理，请稍候...", "info")
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self._start_worker(path)

    def _start_worker(self, path: str):
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        width = self.spin_width.value()
        self.worker = ProcessWorker(path, width)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_processed)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_processed(self, paths: List[str]):
        self.slice_paths = paths
        self.progress_bar.hide()
        self.btn_send.setEnabled(bool(paths))
        self.btn_save.setEnabled(bool(paths))
        self._set_status(f"✅ 已生成 {len(paths)} 张切片，点击「创建 Outlook 邮件」发送", "success")
        self._show_thumbnails(paths)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

    def _on_error(self, msg: str):
        self.progress_bar.hide()
        self._set_status(f"❌ 处理失败: {msg}", "error")
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
            pixmap = QPixmap(path).scaled(120, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            thumb.setPixmap(pixmap)
            self.thumb_grid.addWidget(thumb, row, col)
        self.preview_area.show()

    def _save_slices(self):
        if not self.slice_paths:
            return
        save_dir = QFileDialog.getExistingDirectory(self, "选择保存文件夹", "")
        if not save_dir:
            return
        try:
            for p in self.slice_paths:
                shutil.copy2(p, os.path.join(save_dir, os.path.basename(p)))
            QMessageBox.information(
                self, "保存成功",
                f"已保存 {len(self.slice_paths)} 张切片到：\n{save_dir}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def _send_email(self):
        if not self.slice_paths:
            return
        try:
            width = self.spin_width.value()
            html_content = assemble_html(self.slice_paths, width)
            subject = self.input_subject.text().strip() or "长图邮件"
            create_email_with_images(
                html_content,
                subject=subject,
                to="",
                image_paths=self.slice_paths
            )
            self._set_status("✅ 邮件窗口已打开，请检查后发送", "success")
        except Exception as exc:
            QMessageBox.critical(self, "发送失败", str(exc))

    def _reset_drop_zone(self):
        self.drop_zone.title_label.setText("拖拽图片到此处")
        self.drop_zone.icon_label.setText("📂")
        self.drop_zone.tip_label.setText("支持 JPG · PNG · PDF · PPT，点击上传")

    def reset_app(self):
        self.slice_paths = []
        self.file_path = None
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        self._reset_drop_zone()
        self.input_subject.clear()
        self.spin_width.setValue(Config.DEFAULT_WIDTH)
        self.preview_area.hide()
        self.btn_send.setEnabled(False)
        self.btn_save.setEnabled(False)
        self._set_status("")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(_font())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
