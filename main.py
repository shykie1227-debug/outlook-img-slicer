"""
Outlook 长图无损插入工具 - 主程序 V4
PySide6 窗口应用，支持拖拽上传、自动切片、邮件体积检测、一键复制HTML、多图合并
"""
import os
import sys
import re
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QProgressBar, QMessageBox, QFileDialog,
    QFrame, QGridLayout, QScrollArea,
    QLineEdit, QSlider, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QMimeData
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QFont, QFontMetrics, QKeyEvent, QGuiApplication, QIntValidator

from image_slicer import detect_and_slice, get_image_info, auto_merge_images
from pdf_slicer import pdf_to_images
from ppt_slicer import pptx_to_images
# psd_slicer 依赖 psd_tools + numpy，仅在用户上传 .psd 时懒加载，避免主程序启动报错
# from psd_slicer import psd_to_images
from clickable_map import HotspotMap
from hotspot_editor import HotspotEditorDialog
from html_assembler import assemble_html, generate_plain_html
from outlook_sender import create_email_with_images
from image_safety import check_image_safety, ImageSafetyError, estimate_email_size_mb
from mode_dialog import ProcessModeDialog, MODE_SLICE, MODE_EXPORT, SORT_NATURAL, SORT_DRAG_ORDER


VERSION = "4.6.2"
VERSION_BY = "xiaoming"
MAX_EMAIL_SIZE_MB = 20
COMPRESS_QUALITY = 65  # 压缩时 JPEG 质量


class Config:
    APP_TITLE = f"Outlook 长图助手 V{VERSION}"
    DEFAULT_WIDTH = 960
    MAX_HEIGHT_PER_SLICE = 1728
    MAX_SLICE_COUNT = 20
    WINDOW_WIDTH = 760
    WINDOW_HEIGHT = 720
    SUPPORTED_EXTENSIONS = (
        ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif",
        ".pdf", ".pptx", ".ppt", ".psd", ".psb"
    )


class Theme:
    PRIMARY = "#0078D4"
    PRIMARY_HOVER = "#2563EB"
    PRIMARY_ACTIVE = "#1D4ED8"
    PRIMARY_DISABLED = "#BFDBFE"
    PRIMARY_TEXT = "#FFFFFF"
    SECONDARY_BG = "#FFFFFF"
    SECONDARY_HOVER = "#F3F4F6"
    SECONDARY_BORDER = "#D1D5DB"
    SECONDARY_TEXT = "#374151"
    GHOST_BG = "#F3F4F6"
    GHOST_HOVER = "#E5E7EB"
    GHOST_TEXT = "#374151"
    SUCCESS = "#10B981"
    ERROR = "#EF4444"
    WARNING = "#F59E0B"
    BG = "#F0F2F5"
    CARD = "#FFFFFF"
    BORDER = "#E4E7EC"
    BORDER_HOVER = "#C8CDD6"
    BORDER_FOCUS = "#0078D4"
    TEXT_PRIMARY = "#111827"
    TEXT_SECONDARY = "#6B7280"
    TEXT_PLACEHOLDER = "#9CA3AF"
    TEXT_DISABLED = "#C8CDD6"
    DROPZONE_IDLE_BORDER = "#D1D5DB"
    DROPZONE_HOVER_BG = "#EFF6FF"
    DROPZONE_HOVER_BORDER = "#0078D4"


def _font(family: str = "Microsoft YaHei", size: int = 12, weight: int = QFont.Normal) -> QFont:
    return QFont(family, size, weight)


def _btn_size(text: str, font_size: int = 13, extra_w: int = 36, height: int = 38) -> QSize:
    fm = QFontMetrics(QFont("Microsoft YaHei", font_size))
    return QSize(fm.horizontalAdvance(text) + extra_w, height)


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
        f"QLineEdit {{ background: {Theme.CARD}; color: {Theme.TEXT_PRIMARY}; "
        f"border: 1px solid {Theme.BORDER}; border-radius: 8px; "
        f"padding: 0 12px; font-family: Microsoft YaHei, sans-serif; }}"
        f"QLineEdit:focus {{ border-color: {Theme.BORDER_FOCUS}; }}"
        f"QLineEdit::placeholder {{ color: {Theme.TEXT_PLACEHOLDER}; }}"
    )


# ────────────────────────────────────────────
# 拖放区域
# ────────────────────────────────────────────

class DropZone(QFrame):
    file_dropped = Signal(list)  # 传出多路径列表
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
        self.tip_label = QLabel("支持 JPG · PNG · PDF · PPT · PSD/PSB，点击上传")
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
            f"QFrame {{ background: {bg}; border: 2px dashed {border}; border-radius: 14px; }}"
        )

    def enterEvent(self, event):
        self._hovered = True; self._apply_style(); super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False; self._apply_style(); super().leaveEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._hovered = True
            self._apply_style()
            self.title_label.setText("松开以上传")

    def dragLeaveEvent(self, event):
        self._hovered = False; self._apply_style()
        self.title_label.setText("拖拽图片到此处")

    def dropEvent(self, event: QDropEvent):
        self._hovered = False; self._apply_style()
        if urls := event.mimeData().urls():
            self.file_dropped.emit([u.toLocalFile() for u in urls])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ────────────────────────────────────────────
# 后台处理线程
# ────────────────────────────────────────────

class ProcessWorker(QThread):
    progress = Signal(int)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, file_path: str, width: int, smart: bool = False):
        super().__init__()
        self.file_path = file_path
        self.width = width
        self.smart = smart

    def _convert_and_slice(self, converter_fn, prefix: str, p_before: int, p_after: int) -> List[str]:
        images = converter_fn(self.file_path)
        self.progress.emit(p_before)
        temp_dir = tempfile.gettempdir()
        slice_paths = []
        for index, image in enumerate(images):
            path = os.path.join(temp_dir, f"{prefix}_{index}.png")
            image.save(path)
            slice_paths.append(path)
        self.progress.emit(p_after)
        final = []
        for p in slice_paths:
            final.extend(detect_and_slice(p, max_height=1728, smart=self.smart, target_width=self.width))
        return final

    def run(self):
        try:
            ext = Path(self.file_path).suffix.lower()
            self.progress.emit(15)
            if ext == ".pdf":
                slice_paths = self._convert_and_slice(pdf_to_images, "pdf_page", 45, 75)
            elif ext in (".pptx", ".ppt"):
                slice_paths = self._convert_and_slice(pptx_to_images, "ppt_page", 45, 75)
            elif ext in (".psd", ".psb"):
                # 懒加载 psd_slicer，依赖 psd_tools + numpy
                from psd_slicer import psd_to_images
                slice_paths = self._convert_and_slice(psd_to_images, "psd_page", 45, 75)
            else:
                slice_paths = detect_and_slice(self.file_path, max_height=1728, smart=self.smart, target_width=self.width)
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
        self.worker: Optional[ProcessWorker] = None
        self.hotspot_map = HotspotMap()
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle(Config.APP_TITLE)
        self.setMinimumSize(720, 720)
        self.resize(Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)

        container = QWidget()
        self.setCentralWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)

        # ══ Header ════════════════════════════
        title = QLabel(f"Outlook 长图助手 V{VERSION}")
        title.setFont(_font("Microsoft YaHei", 20, QFont.Bold))
        title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        root.addWidget(title)

        subtitle = QLabel("长图/PDF/PPT切片后插入Outlook邮件，保持原始清晰度")
        subtitle.setFont(_font("Microsoft YaHei", 12))
        subtitle.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        root.addWidget(subtitle)

        # ══ Drop Zone ════════════════════════
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._handle_dropped_files)
        self.drop_zone.clicked.connect(self._select_file)
        root.addWidget(self.drop_zone)

        # ══ 工具栏（重置 + 宽度 + 复制HTML） ═══
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.btn_reset = QPushButton("🔄 重置")
        self.btn_reset.setFont(_font("Microsoft YaHei", 12))
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet(_btn_ghost())
        self.btn_reset.setFixedSize(_btn_size("🔄 重置", 12, extra_w=20, height=34))
        self.btn_reset.clicked.connect(self.reset_app)
        toolbar.addWidget(self.btn_reset)

        width_lbl = QLabel("宽度：")
        width_lbl.setFont(_font("Microsoft YaHei", 12))
        width_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        toolbar.addWidget(width_lbl)

        self.edit_width = QLineEdit(f"{Config.DEFAULT_WIDTH}")
        self.edit_width.setFont(_font("Microsoft YaHei", 12))
        self.edit_width.setValidator(QIntValidator(400, 1920))
        self.edit_width.setFixedWidth(100)
        self.edit_width.setFixedHeight(34)
        self.edit_width.setAlignment(Qt.AlignCenter)
        self.edit_width.setStyleSheet(
            f"QLineEdit {{ background: {Theme.CARD}; color: {Theme.TEXT_PRIMARY}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 8px; "
            f"padding: 0 8px; font-family: Microsoft YaHei, sans-serif; }}"
            f"QLineEdit:focus {{ border-color: {Theme.BORDER_FOCUS}; }}"
        )
        self.edit_width.editingFinished.connect(self._on_width_edited)
        px_lbl = QLabel("px")
        px_lbl.setFont(_font("Microsoft YaHei", 12))
        px_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        toolbar.addWidget(self.edit_width)
        toolbar.addWidget(px_lbl)

        self.slider_width = QSlider(Qt.Horizontal)
        self.slider_width.setRange(400, 1920)
        self.slider_width.setValue(Config.DEFAULT_WIDTH)
        self.slider_width.setFixedWidth(160)
        self.slider_width.setFixedHeight(34)
        self.slider_width.setStyleSheet(
            f"QSlider::groove:horizontal {{ background: {Theme.BORDER}; height: 6px; border-radius: 3px; }}"
            f"QSlider::handle:horizontal {{ background: {Theme.PRIMARY}; width: 18px; height: 18px; "
            f"margin: -6px 0; border-radius: 9px; }}"
            f"QSlider::sub-page:horizontal {{ background: {Theme.PRIMARY}; height: 6px; border-radius: 3px; }}"
        )
        self.slider_width.valueChanged.connect(self._on_slider_changed)
        toolbar.addWidget(self.slider_width)

        toolbar.addStretch()
        root.addLayout(toolbar)

        # ══ 第二行：智能切图 + 复制HTML（右对齐） ═══
        toolbar2 = QHBoxLayout()
        toolbar2.setSpacing(10)

        self.chk_smart = QCheckBox("智能切图")
        self.chk_smart.setFont(_font("Microsoft YaHei", 12))
        self.chk_smart.setChecked(False)  # 默认等分切图
        self.chk_smart.setCursor(Qt.PointingHandCursor)
        self.chk_smart.setStyleSheet(
            f"QCheckBox {{ color: {Theme.TEXT_SECONDARY}; background: transparent; spacing: 6px; }}"
            f"QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; "
            f"border: 1px solid {Theme.BORDER}; background: {Theme.CARD}; }}"
            f"QCheckBox::indicator:checked {{ background: {Theme.PRIMARY}; "
            f"border-color: {Theme.PRIMARY}; }}"
        )
        toolbar2.addWidget(self.chk_smart)

        self.btn_copy_html = QPushButton("📋 复制HTML")
        self.btn_copy_html.setFont(_font("Microsoft YaHei", 12))
        self.btn_copy_html.setCursor(Qt.PointingHandCursor)
        self.btn_copy_html.setEnabled(False)
        self.btn_copy_html.setStyleSheet(_btn_ghost())
        self.btn_copy_html.setFixedSize(_btn_size("📋 复制HTML", 12, extra_w=20, height=34))
        self.btn_copy_html.clicked.connect(self._copy_html)
        toolbar2.addWidget(self.btn_copy_html)

        self.btn_hotspot = QPushButton("🎯 添加可点击按钮")
        self.btn_hotspot.setFont(_font("Microsoft YaHei", 12))
        self.btn_hotspot.setCursor(Qt.PointingHandCursor)
        self.btn_hotspot.setEnabled(False)
        self.btn_hotspot.setStyleSheet(_btn_ghost())
        self.btn_hotspot.setFixedSize(_btn_size("🎯 添加可点击按钮", 12, extra_w=20, height=34))
        self.btn_hotspot.setToolTip("为切片添加可点击热区，在邮件中点圈位置跳转 URL")
        self.btn_hotspot.clicked.connect(self._open_hotspot_editor)
        toolbar2.addWidget(self.btn_hotspot)

        toolbar2.addStretch()
        root.addLayout(toolbar2)

        # ══ 邮件标题 ════════════════════════
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

        # ══ 预览区 ═════════════════════════
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

        # ══ 进度条 ═════════════════════════
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ border: none; background: {Theme.BORDER}; border-radius: 2px; }}"
            f"QProgressBar::chunk {{ background: {Theme.PRIMARY}; border-radius: 2px; }}"
        )
        self.progress_bar.hide()
        root.addWidget(self.progress_bar)

        # ══ 状态 ═══════════════════════════
        self.status_label = QLabel("")
        self.status_label.setFont(_font("Microsoft YaHei", 12))
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        root.addWidget(self.status_label)

        # ══ 底部按钮区 ═════════════════════
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.setContentsMargins(0, 4, 0, 0)

        self.btn_send = QPushButton("创建 Outlook 邮件")
        self.btn_send.setFont(_font("Microsoft YaHei", 14, QFont.Bold))
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setEnabled(False)
        self.btn_send.setStyleSheet(_btn_primary())
        self.btn_send.setFixedHeight(44)
        self.btn_send.clicked.connect(self._send_email)

        self.btn_save = QPushButton("保存切图")
        self.btn_save.setFont(_font("Microsoft YaHei", 13, QFont.Medium))
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setEnabled(False)
        self.btn_save.setStyleSheet(_btn_secondary())
        self.btn_save.setFixedHeight(44)
        self.btn_save.clicked.connect(self._save_slices)

        btn_row.addWidget(self.btn_send, stretch=5)
        btn_row.addWidget(self.btn_save, stretch=5)
        root.addLayout(btn_row)

        # ══ 版本 ═══════════════════════════
        ver_row = QHBoxLayout()
        ver_row.addStretch()
        ver_col = QVBoxLayout()
        ver_col.setSpacing(0)
        ver1 = QLabel(f"V{VERSION}")
        ver1.setFont(_font("Microsoft YaHei", 11, QFont.Bold))
        ver1.setStyleSheet(f"color: {Theme.TEXT_PLACEHOLDER}; background: transparent;")
        ver1.setAlignment(Qt.AlignRight)
        ver2 = QLabel(VERSION_BY)
        ver2.setFont(_font("Microsoft YaHei", 10))
        ver2.setStyleSheet(f"color: {Theme.TEXT_PLACEHOLDER}; background: transparent;")
        ver2.setAlignment(Qt.AlignRight)
        ver_col.addWidget(ver1)
        ver_col.addWidget(ver2)
        ver_row.addLayout(ver_col)
        root.addLayout(ver_row)

    # ── 工具函数 ────────────────────────────
    def _get_width(self) -> int:
        try:
            return int(self.edit_width.text())
        except ValueError:
            return Config.DEFAULT_WIDTH

    def _set_status(self, text: str, level: str = "info"):
        colors = {"info": Theme.TEXT_SECONDARY, "success": Theme.SUCCESS,
                  "error": Theme.ERROR, "warning": Theme.WARNING}
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {colors.get(level, Theme.TEXT_SECONDARY)}; "
            f"font-size: 12px; background: transparent;"
        )

    def _reset_drop_zone(self):
        self.drop_zone.title_label.setText("拖拽图片到此处")
        self.drop_zone.icon_label.setText("📂")
        self.drop_zone.tip_label.setText("支持 JPG · PNG · PDF · PPT · PSD/PSB，点击上传")

    def _on_width_edited(self):
        """手动输入完成时同步到滑块，超限弹窗提醒"""
        try:
            v = int(self.edit_width.text())
            if v < 400:
                QMessageBox.warning(self, "宽度超限", "宽度最小为 400px，已自动调整为 400px")
                v = 400
            elif v > 1920:
                QMessageBox.warning(self, "宽度超限", "宽度最大为 1920px，已自动调整为 1920px")
                v = 1920
            self.slider_width.blockSignals(True)
            self.slider_width.setValue(v)
            self.slider_width.blockSignals(False)
            self.edit_width.setText(str(v))
        except ValueError:
            self.edit_width.setText(str(self.slider_width.value()))

    def _on_slider_changed(self, value: int):
        """滑块拖动时同步到输入框"""
        self.edit_width.setText(str(value))

    # ── 快捷键 ──────────────────────────────
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

    # ── 文件输入 ────────────────────────────
    def _select_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片、PDF 或 PPT", "",
            "图片 (*.jpg *.jpeg *.png *.bmp *.webp *.gif);;PDF (*.pdf);;PPT/PPTX (*.pptx *.ppt);;PSD/PSB (*.psd *.psb)"
        )
        if paths:
            self._handle_dropped_files(paths)

    def _paste_image(self):
        image = QGuiApplication.clipboard().image()
        if image is None or image.isNull():
            QMessageBox.warning(self, "粘贴失败", "剪贴板中没有图片内容。")
            return
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"paste_{os.getpid()}.png")
        image.save(temp_path)
        self._handle_dropped_files([temp_path])

    def _handle_dropped_files(self, paths: List[str]):
        """
        入口：处理一次拖入/选择的一批文件。
        V4.6.2 重构：拖入后弹「处理模式选择」弹窗（切图 / 图片导出 + 排序 + 保存路径）。
        """
        # 过滤合法后缀
        valid = [p for p in paths if Path(p).suffix.lower() in Config.SUPPORTED_EXTENSIONS]
        if not valid:
            QMessageBox.warning(self, "格式不支持", "请选择图片、PDF、PPT 或 PSD/PSB 文件。")
            return

        # 弹模式选择弹窗（V4.6.2 新增）
        dlg = ProcessModeDialog(valid, self)
        if dlg.exec() != QDialog.Accepted:
            return  # 用户取消

        result = dlg.get_result()
        mode = result["mode"]
        sort_mode = result["sort_mode"]
        save_dir = result["save_dir"]

        # 按选择的排序方式排序
        if sort_mode == SORT_NATURAL:
            def natural_key(s):
                return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', Path(s).stem)]
            valid = sorted(valid, key=natural_key)
        # SORT_DRAG_ORDER: 保持拖入顺序，不排序

        # 路由
        if mode == MODE_SLICE:
            # 切图模式：原 V4.6.1 路径
            if len(valid) == 1:
                self._start_processing(valid[0], save_dir=save_dir)
            else:
                # 多图：走原有的「智能拼图」弹窗
                self._handle_multi_files(valid, save_dir=save_dir)
        elif mode == MODE_EXPORT:
            # 图片导出模式：V4.6.2 新增
            self._export_images(valid, save_dir=save_dir)

    def _handle_multi_files(self, paths: List[str]):
        """多张图片 → 弹框询问是否智能拼图"""
        btn_box = QMessageBox(self)
        btn_box.setWindowTitle("智能拼图")
        btn_box.setIcon(QMessageBox.Question)
        btn_box.setText(f"检测到 {len(paths)} 张图片")
        btn_box.setInformativeText(
            "智能拼图将多张图片纵向拼接为一张长图，<b>保存后可继续拖入新图</b>"
        )
        btn_merge = btn_box.addButton("🗜️ 智能拼图", QMessageBox.AcceptRole)
        btn_single = btn_box.addButton("📄 只取第一张", QMessageBox.NoRole)
        btn_cancel = btn_box.addButton("取消", QMessageBox.RejectRole)
        btn_box.setDefaultButton(btn_merge)
        btn_box.exec()
        if btn_box.clickedButton() == btn_cancel:
            return
        if btn_box.clickedButton() == btn_single:
            # 仅处理第一张
            self._start_processing(paths[0], save_dir=save_dir)
            self._set_status("💡 多图模式下仅处理了第一张图片，其余已忽略", "info")
            return

        # ── 智能拼图 ──────────────────────────
        self._set_status("正在智能拼接多张图片...", "info")
        try:
            merged_path = auto_merge_images(paths, direction="vertical")
            # V4.6.2 优化：主弹窗已选的保存路径优先；否则再问
            if not save_dir:
                save_dir = QFileDialog.getExistingDirectory(self, "选择保存合并图片的位置", "")
            if not save_dir:
                QMessageBox.information(self, "提示", "已取消保存，合并后的图片仅用于本次临时切片。")
            else:
                # 保留原文件格式，不强制改 .jpg
                src_ext = Path(merged_path).suffix.lower() or ".jpg"
                fname = f"merged_{os.getpid()}{src_ext}"
                save_path = os.path.join(save_dir, fname)
                shutil.copy2(merged_path, save_path)
                self._set_status(f"✅ 合并图片已保存至：{save_path}", "success")

            # 合并完成，清空拖拽区
            self.reset_app()
            self._set_status(f"✅ 合并图片已保存，可继续拖入新图片", "success")
        except Exception as exc:
            QMessageBox.critical(self, "拼图失败", str(exc))

    def _export_images(self, paths: List[str], save_dir: Optional[str] = None):
        """图片导出模式：多图合并为长图，或单图直接保存到指定路径。"""
        self._set_status("正在图片导出...", "info")
        try:
            if len(paths) == 1:
                # 单张：直接复制到保存目录（或临时目录）
                result_path = paths[0]
            else:
                # 多张：合并为长图
                result_path = auto_merge_images(paths, direction="vertical")

            if save_dir:
                dst = os.path.join(save_dir, Path(result_path).name)
                shutil.copy2(result_path, dst)
                QMessageBox.information(self, "导出成功",
                    f"✅ 图片已导出至：\n{dst}")
                self._set_status(f"✅ 图片已导出至：{dst}", "success")
            else:
                QMessageBox.information(self, "导出完成",
                    f"✅ 图片已合并（未指定保存路径，用临时目录）")
                self._set_status("✅ 图片导出完成", "success")

            self.reset_app()
            self._set_status("✅ 导出完成，可继续拖入新图片", "success")
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", str(exc))

    def _start_processing(self, path: str, save_dir: Optional[str] = None):
        """单图/合并后处理的统一入口"""
        ext = Path(path).suffix.lower()
        # 安全检查
        if ext not in (".pdf", ".pptx", ".ppt", ".psd", ".psb"):
            try:
                check_image_safety(path)
            except ImageSafetyError as e:
                reply = QMessageBox.warning(
                    self, "图片安全检查未通过",
                    f"{e}\n\n是否仍要处理？（可能导致程序卡死）",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return

        # 检查切片数量
        if ext not in (".pdf", ".pptx", ".ppt", ".psd", ".psb"):
            try:
                info = get_image_info(path)
                sc = (info["height"] + Config.MAX_HEIGHT_PER_SLICE - 1) // Config.MAX_HEIGHT_PER_SLICE
                sc = max(1, sc)
                if sc > Config.MAX_SLICE_COUNT:
                    reply = QMessageBox.warning(
                        self, "切片数量较多",
                        f"当前图片预计生成 <b>{sc}</b> 张切片（> {Config.MAX_SLICE_COUNT}），是否继续？",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                    )
                    if reply != QMessageBox.Yes:
                        return
            except Exception:
                pass

        self.file_path = path
        self.drop_zone.title_label.setText(Path(path).name)
        self.drop_zone.icon_label.setText("✅")
        self.drop_zone.tip_label.setText("正在切片处理...")
        self._set_status("正在处理，请稍候...", "info")
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self._start_worker(path)

    def _start_worker(self, path: str):
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        self.worker = ProcessWorker(path, self._get_width(), smart=self.chk_smart.isChecked())
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_processed)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_processed(self, paths: List[str]):
        self.slice_paths = paths
        self.progress_bar.hide()
        self.btn_send.setEnabled(bool(paths))
        self.btn_save.setEnabled(bool(paths))
        self.btn_copy_html.setEnabled(bool(paths))
        self.btn_hotspot.setEnabled(bool(paths))
        # 重新处理时清空旧热区
        self.hotspot_map.clear()

        # 体积检测
        size_mb = estimate_email_size_mb(paths) if paths else 0
        self._set_status(
            f"✅ 已生成 {len(paths)} 张切片 | 预计 {size_mb}MB"
            + (" ⚠️ 超过推荐大小(20MB)，发送时可选择压缩" if size_mb > MAX_EMAIL_SIZE_MB else ""),
            "warning" if size_mb > MAX_EMAIL_SIZE_MB else "success"
        )
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
                f"background: {Theme.CARD}; border-radius: 8px; border: 1px solid {Theme.BORDER};"
                f"QToolTip {{ background: #1D1D1F; color: white; border: none; padding: 4px 8px; }}"
            )
            pixmap = QPixmap(path).scaled(120, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            thumb.setPixmap(pixmap)
            thumb.setToolTip(f"切片 {i + 1}: {Path(path).name}\n点击编辑可点击按钮")
            thumb.setCursor(Qt.PointingHandCursor)
            thumb.mousePressEvent = lambda ev, p=path, idx=i: self._on_thumb_clicked(ev, p, idx)
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

    def _copy_html(self):
        """复制 HTML 到剪贴板（同时写入 HTML 和纯文本格式）"""
        if not self.slice_paths:
            return
        try:
            html = generate_plain_html(
                self.slice_paths, self._get_width(),
                hotspots=self.hotspot_map if not self.hotspot_map.is_empty() else None,
            )
            mime = QMimeData()
            # HTML 格式：Outlook/Word 粘贴时正确渲染
            mime.setHtml(html)
            # 纯文本格式：作为 fallback
            plain = f"已将 {len(self.slice_paths)} 张切片 HTML 复制到剪贴板"
            mime.setText(plain)
            QGuiApplication.clipboard().setMimeData(mime)
            self._set_status("📋 HTML 已复制（支持 Outlook/Word 直接粘贴渲染）", "success")
        except Exception as exc:
            QMessageBox.critical(self, "复制失败", str(exc))

    def _compress_slices(self):
        """
        将切片压缩为较低品质的 JPEG，原地替换。

        基于开源项目实现:
        - Pillow (python-pillow/Pillow ⭐13k) https://github.com/python-pillow/Pillow
          JPEG 压缩: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg
        - MozJPEG (mozilla/mozjpeg ⭐2.8k) 感知量化表
          https://github.com/mozilla/mozjpeg
        """
        if not self.slice_paths:
            return
        from PIL import Image
        for i, p in enumerate(self.slice_paths):
            img = Image.open(p)
            rgb = img.convert("RGB") if img.mode in ("RGBA", "P") else img
            # 直接保存为 JPEG 并用回 PNG 扩展名，避免路径引用失效
            new_path = p.replace(".png", ".jpg")
            rgb.save(new_path, format="JPEG", quality=COMPRESS_QUALITY, optimize=True)
            self.slice_paths[i] = new_path

    def _send_email(self):
        if not self.slice_paths:
            return

        # 体积检测 + 压缩询问
        size_mb = estimate_email_size_mb(self.slice_paths)
        if size_mb > MAX_EMAIL_SIZE_MB:
            btn_box = QMessageBox(self)
            btn_box.setWindowTitle("邮件体积较大")
            btn_box.setIcon(QMessageBox.Warning)
            btn_box.setText(f"预计 {size_mb}MB，超过推荐限制（{MAX_EMAIL_SIZE_MB}MB）")
            btn_box.setInformativeText(
                f"<b>压缩后</b> 缩小至约 {COMPRESS_QUALITY}% 品质（推荐）\n"
                f"<b>原画质</b> 保持当前品质直接发送"
            )
            btn_compress = btn_box.addButton(f"🔽 压缩至 {COMPRESS_QUALITY}%", QMessageBox.AcceptRole)
            btn_original = btn_box.addButton("🎨 原画质发送", QMessageBox.NoRole)
            btn_cancel = btn_box.addButton("取消", QMessageBox.RejectRole)
            btn_box.setDefaultButton(btn_compress)
            btn_box.exec()
            if btn_box.clickedButton() == btn_cancel:
                self._set_status(
                    "💡 已取消发送，可先「保存切图」手动压缩后再编辑",
                    "warning"
                )
                return
            if btn_box.clickedButton() == btn_compress:
                self._compress_slices()
                self._set_status(
                    f"🔽 已压缩至约 {estimate_email_size_mb(self.slice_paths)}MB，正在打开邮件...",
                    "success"
                )

        try:
            html_content = assemble_html(
                self.slice_paths, self._get_width(),
                hotspots=self.hotspot_map if not self.hotspot_map.is_empty() else None,
            )
            subject = self.input_subject.text().strip() or "长图邮件"
            create_email_with_images(
                html_content, subject=subject, to="", image_paths=self.slice_paths
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
        self.hotspot_map.clear()
        self._reset_drop_zone()
        self.input_subject.clear()
        self.edit_width.setText(str(Config.DEFAULT_WIDTH))
        self.slider_width.setValue(Config.DEFAULT_WIDTH)
        self.preview_area.hide()
        self.btn_send.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.btn_copy_html.setEnabled(False)
        self.btn_hotspot.setEnabled(False)
        self._set_status("")

    def _on_thumb_clicked(self, ev, path: str, idx: int):
        """点击缩略图 → 打开热区编辑器"""
        if ev.button() == Qt.LeftButton:
            self._open_hotspot_editor_for_slice(path)

    def _open_hotspot_editor(self):
        """「添加可点击按钮」按钮 → 弹出切片选择 + 打开编辑器"""
        if not self.slice_paths:
            return
        if len(self.slice_paths) == 1:
            self._open_hotspot_editor_for_slice(self.slice_paths[0])
            return
        # 多切片：弹窗让用户选一个
        from PySide6.QtWidgets import QInputDialog
        items = [f"切片 {i + 1}: {Path(p).name}" for i, p in enumerate(self.slice_paths)]
        choice, ok = QInputDialog.getItem(
            self, "选择要编辑的切片", "为哪个切片添加可点击按钮？", items, 0, False
        )
        if not ok:
            return
        idx = items.index(choice)
        self._open_hotspot_editor_for_slice(self.slice_paths[idx])

    def _open_hotspot_editor_for_slice(self, slice_path: str):
        dlg = HotspotEditorDialog(slice_path, self.hotspot_map, self)
        dlg.exec()
        # 同步热区状态提示
        if not self.hotspot_map.is_empty():
            self._set_status(
                f"🎯 已为 {len(self.hotspot_map.all_slices())} 个切片添加共 "
                f"{self.hotspot_map.total_count()} 个可点击按钮",
                "success",
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(_font())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
