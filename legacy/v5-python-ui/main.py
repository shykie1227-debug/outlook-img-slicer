"""
Outlook 长图无损插入工具 - 主程序 V5
PySide6 窗口应用，支持拖拽上传、自动切片、邮件体积检测、一键复制HTML、多图合并
"""
import os
import sys
import re
import time
import tempfile
import shutil
import traceback
from pathlib import Path
from typing import Optional, List, Dict

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QProgressBar, QMessageBox, QFileDialog,
    QFrame, QGridLayout, QScrollArea,
    QLineEdit, QSlider, QCheckBox, QDialog
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QMimeData
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QFont, QFontMetrics, QKeyEvent, QGuiApplication, QIntValidator, QIcon

from image_slicer import (
    detect_and_slice,
    get_image_info,
    reslice_existing_stack,
    cleanup_generated_slices,
)
# V4.7.7 Fix E: 删除 auto_merge_images 死 import（原 _handle_multi_files 已删）
# image_slicer.auto_merge_images 函数本身保留以备未来使用
from pdf_slicer import pdf_to_images
from ppt_slicer import pptx_to_images
# psd_slicer 依赖 psd_tools + numpy，仅在用户上传 .psd 时懒加载，避免主程序启动报错
# from psd_slicer import psd_to_images
from clickable_map import HotspotMap, Hotspot
from hotspot_editor import HotspotEditorDialog
from html_assembler import (
    assemble_html, generate_plain_html, materialize_display_slices_strict,
    SliceItem, cleanup_temp_slices,
    _group_by_source, _is_plain_vertical_stack,
)
from hotspot_slicer import slice_paths_by_hotspots
from outlook_sender import create_email_with_images
from image_safety import check_image_safety, ImageSafetyError, estimate_email_size_mb
# V4.7.7 Fix E: 移除 mode_dialog 引用，模式选择改为面板 chk_export_mode toggle。
# ProcessModeDialog 类保留在 mode_dialog.py 中以便 v4.6.2-v4.7.6 用户回退，
# 不再从 main.py 调用。
from export_dialog import ExportFormatDialog, FMT_PNG, FMT_JPG
from clipboard_html import (
    build_windows_clipboard_html as _build_windows_clipboard_html,
)
from cut_editor import CutEditorDialog
import os

# ── 图标加载 ────────────────────────────────
_ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

def _icon(name: str, size: int = 20, color: str | None = None) -> QIcon:
    """Load an SVG icon from the icons directory.

    Args:
        name: Icon filename without .svg extension (e.g. 'upload-cloud')
        size: Not used by QIcon directly, for reference only
        color: Optional hex color to dynamically tint the icon (e.g. '#0065fd')
               Will try name-color variant first, then dynamically recolor.
    """
    # Try color variant first (e.g. 'check-blue')
    if color:
        variant_name = f"{name}-{_color_name(color)}"
        variant_path = os.path.join(_ICONS_DIR, f"{variant_name}.svg")
        if os.path.exists(variant_path):
            return QIcon(variant_path)

    path = os.path.join(_ICONS_DIR, f"{name}.svg")
    if os.path.exists(path):
        if color:
            return _tinted_icon(path, color)
        return QIcon(path)
    return QIcon()


def _color_name(hex_color: str) -> str:
    """Map hex colors to short names for variant file lookup."""
    mapping = {
        "#0065fd": "blue",
        "#7f8d9f": "muted",
        "#ef4444": "red",
        "#f59e0b": "yellow",
        "#10b981": "green",
        "#0e1115": "dark",
    }
    return mapping.get(hex_color.lower(), hex_color.lstrip("#"))


def _tinted_icon(svg_path: str, color: str) -> QIcon:
    """Dynamically recolor an SVG icon by replacing stroke attributes."""
    try:
        with open(svg_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Replace stroke colors with the new color
        import re
        tinted = re.sub(r'stroke="[^"]*"', f'stroke="{color}"', content)
        tinted = re.sub(r'fill="currentColor"', f'fill="{color}"', tinted)
        # Write to a temp file
        tmp_path = svg_path + f".tinted.{color.lstrip('#')}.svg"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(tinted)
        icon = QIcon(tmp_path)
        return icon
    except Exception:
        return QIcon(svg_path)


VERSION = "6.0.3"
VERSION_BY = "xiaoming"
# V6.0: Electron + React 重构，SVG 支持，Outlook 兼容性修复。
HOTSPOT_FEATURE_ENABLED = True
OUTLOOK_SAFE_MAX_HEIGHT_PER_SLICE = 1200
MAX_EMAIL_SIZE_MB = 20
COMPRESS_QUALITY = 65  # 压缩时 JPEG 质量


class Config:
    APP_TITLE = f"Outlook 长图助手 V{VERSION}"
    DEFAULT_WIDTH = 650
    MAX_HEIGHT_PER_SLICE = OUTLOOK_SAFE_MAX_HEIGHT_PER_SLICE
    MAX_SLICE_COUNT = 20
    WINDOW_WIDTH = 760
    WINDOW_HEIGHT = 720
    SUPPORTED_EXTENSIONS = (
        ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif",
        ".pdf", ".pptx", ".ppt", ".psd", ".psb"
    )


class Theme:
    PRIMARY = "#0065fd"
    PRIMARY_HOVER = "#0057da"
    PRIMARY_ACTIVE = "#0043ad"
    PRIMARY_DISABLED = "#e5e9ff"
    PRIMARY_TEXT = "#ffffff"
    SECONDARY_BG = "#ffffff"
    SECONDARY_HOVER = "#eff1f4"
    SECONDARY_BORDER = "#e7eaef"
    SECONDARY_TEXT = "#0e1115"
    GHOST_BG = "#eff1f4"
    GHOST_HOVER = "#dde1e8"
    GHOST_TEXT = "#0e1115"
    SUCCESS = "#10b981"
    ERROR = "#ef4444"
    WARNING = "#f59e0b"
    BG = "#ffffff"
    CARD = "#f9f9fa"
    CARD_SHADOW = "rgba(0, 0, 0, 0.04)"
    BORDER = "#e7eaef"
    BORDER_HOVER = "#d0d5dd"
    BORDER_FOCUS = "#557fff"
    TEXT_PRIMARY = "#0e1115"
    TEXT_SECONDARY = "#333942"
    TEXT_PLACEHOLDER = "#7f8d9f"
    TEXT_DISABLED = "#b0b8c4"
    DROPZONE_IDLE_BORDER = "#e7eaef"
    DROPZONE_HOVER_BG = "#e5e9ff"
    DROPZONE_HOVER_BORDER = "#0065fd"


def _load_psd_images(psd_path: str):
    """按需加载 PSD/PSB 渲染器，避免主程序启动时强依赖 psd-tools。"""
    from psd_slicer import psd_to_images
    return psd_to_images(psd_path)


def _render_source_to_images(path: str):
    """
    将任意受支持的输入文件渲染为 PIL Image 列表。

    图片：直接读取
    PDF：逐页渲染
    PPT/PPTX：逐页渲染
    PSD/PSB：展平图层后渲染
    """
    ext = Path(path).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"):
        from PIL import Image as PILImage
        with PILImage.open(path) as img:
            return [img.convert("RGBA") if img.mode == "RGBA" else img.convert("RGB")]
    if ext == ".pdf":
        return pdf_to_images(path)
    if ext in (".ppt", ".pptx"):
        return pptx_to_images(path)
    if ext in (".psd", ".psb"):
        return _load_psd_images(path)
    raise ValueError(f"不支持的导出格式: {path}")


def _font(family: str = "Microsoft YaHei", size: int = 12, weight: int = QFont.Normal) -> QFont:
    return QFont(family, size, weight)


def _btn_size(text: str, font_size: int = 13, extra_w: int = 36, height: int = 38) -> QSize:
    fm = QFontMetrics(QFont("Microsoft YaHei", font_size))
    return QSize(fm.horizontalAdvance(text) + extra_w, height)


def _btn_primary() -> str:
    return (
        f"QPushButton {{ background: {Theme.PRIMARY}; color: {Theme.PRIMARY_TEXT}; "
        f"border: none; border-radius: 999px; font-weight: 500; font-family: Microsoft YaHei, sans-serif;}}"
        f"QPushButton:hover {{ background: {Theme.PRIMARY_HOVER}; }}"
        f"QPushButton:pressed {{ background: {Theme.PRIMARY_ACTIVE}; }}"
        f"QPushButton:disabled {{ background: {Theme.PRIMARY_DISABLED}; color: {Theme.TEXT_PLACEHOLDER}; }}"
    )


def _btn_secondary() -> str:
    return (
        f"QPushButton {{ background: {Theme.SECONDARY_BG}; color: {Theme.SECONDARY_TEXT}; "
        f"border: 1px solid {Theme.SECONDARY_BORDER}; border-radius: 999px; "
        f"font-family: Microsoft YaHei, sans-serif;}}"
        f"QPushButton:hover {{ background: {Theme.SECONDARY_HOVER}; border-color: {Theme.BORDER_HOVER}; }}"
        f"QPushButton:disabled {{ color: {Theme.TEXT_DISABLED}; border-color: {Theme.BORDER}; }}"
    )


def _btn_ghost() -> str:
    return (
        f"QPushButton {{ background: {Theme.GHOST_BG}; color: {Theme.GHOST_TEXT}; "
        f"border: none; border-radius: 999px; "
        f"font-family: Microsoft YaHei, sans-serif;}}"
        f"QPushButton:hover {{ background: {Theme.GHOST_HOVER}; }}"
        f"QPushButton:disabled {{ color: {Theme.TEXT_DISABLED}; }}"
    )


def _input_style() -> str:
    return (
        f"QLineEdit {{ background: {Theme.CARD}; color: {Theme.TEXT_PRIMARY}; "
        f"border: 1px solid {Theme.BORDER}; border-radius: 8px; "
        f"padding: 0 12px; font-family: Microsoft YaHei, sans-serif;}}"
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
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(28, 32, 28, 32)
        self.content_layout.setSpacing(10)
        self.content_layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setPixmap(_icon("upload-cloud", 44).pixmap(44, 44))
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        self.title_label = QLabel("拖拽图片到此处")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(_font("Microsoft YaHei", 14, QFont.Bold))
        self.title_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;")
        self.tip_label = QLabel("支持 JPG · PNG · PDF · PPT · PSD/PSB，点击上传")
        self.tip_label.setAlignment(Qt.AlignCenter)
        self.tip_label.setFont(_font("Microsoft YaHei", 12))
        self.tip_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent; border: none;")

        self.content_layout.addWidget(self.icon_label)
        self.content_layout.addWidget(self.title_label)
        self.content_layout.addWidget(self.tip_label)

    def set_compact(self, compact: bool):
        """Collapse the large drop target after processing so previews stay visible."""
        if compact:
            self.icon_label.hide()
            self.content_layout.setContentsMargins(16, 7, 16, 7)
            self.content_layout.setSpacing(2)
            self.setMinimumHeight(72)
            self.setMaximumHeight(72)
        else:
            self.icon_label.show()
            self.content_layout.setContentsMargins(28, 32, 28, 32)
            self.content_layout.setSpacing(10)
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)

    def _apply_style(self):
        border = Theme.DROPZONE_HOVER_BORDER if self._hovered else Theme.DROPZONE_IDLE_BORDER
        bg = Theme.DROPZONE_HOVER_BG if self._hovered else Theme.CARD
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border: 2px dashed {border}; border-radius: 12px; }}"
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
        # V4.8.7: 100 页 PDF 会在 %TEMP% 永久留 100 个 png，
        # 改用独立临时目录，结束统一 rmtree。
        work_dir = tempfile.mkdtemp(prefix="outlook_slicer_convert_")
        try:
            images = converter_fn(self.file_path)
            self.progress.emit(p_before)
            slice_paths = []
            for index, image in enumerate(images):
                path = os.path.join(work_dir, f"{prefix}_{index}.png")
                image.save(path)
                slice_paths.append(path)
                # 释放 PIL Image 引用，避免百页大文件内存峰值
                del image
            self.progress.emit(p_after)
            final = []
            for p in slice_paths:
                final.extend(detect_and_slice(
                    p, max_height=OUTLOOK_SAFE_MAX_HEIGHT_PER_SLICE,
                    smart=self.smart, target_width=self.width,
                    always_copy=True,
                ))
            # 切片结果已生成在工作目录，把原图删了（切片 PNG 会保留供后续步骤）
            for p in slice_paths:
                try:
                    os.remove(p)
                except OSError:
                    pass
            # final 路径在工作目录里，留给 send/copy 时再用，最后由 atexit 兜底
            return final
        finally:
            # detect_and_slice 的最终输出位于独立工作区，转换中间页可立即清理。
            shutil.rmtree(work_dir, ignore_errors=True)

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
                slice_paths = detect_and_slice(
                    self.file_path, max_height=OUTLOOK_SAFE_MAX_HEIGHT_PER_SLICE,
                    smart=self.smart, target_width=self.width
                )
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
        # V4.6.7 排序架构：原切片的 source_index 映射
        # key = slice 文件名，value = source_index（浮点：原切片=整数，Hotspot派生=整数+N*0.001）
        # **不依赖** slice_paths 顺序、文件名、目录遍历
        self.slice_source_index: Dict[str, float] = {}
        self.worker: Optional[ProcessWorker] = None
        self.hotspot_map = HotspotMap()
        self.last_export_dir: Optional[str] = None
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

        self.guide_label = QLabel(
            "1  放入文件    →    2  调整切线 / 添加链接    →    3  创建邮件"
        )
        self.guide_label.setFont(_font("Microsoft YaHei", 11, QFont.Medium))
        self.guide_label.setStyleSheet(
            f"color: {Theme.TEXT_SECONDARY}; background: {Theme.GHOST_BG}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 999px; "
            f"padding: 8px 12px;"
        )
        self.guide_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self.guide_label)

        # ══ Drop Zone ════════════════════════
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._handle_dropped_files)
        self.drop_zone.clicked.connect(self._select_file)
        root.addWidget(self.drop_zone)

        # ══ 工具栏（重置 + 宽度 + 复制HTML） ═══
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.btn_reset = QPushButton(" 重置")
        self.btn_reset.setFont(_font("Microsoft YaHei", 12))
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet(_btn_ghost())
        self.btn_reset.setIcon(_icon("rotate-ccw", 18))
        self.btn_reset.setIconSize(QSize(18, 18))
        self.btn_reset.setFixedSize(_btn_size(" 重置", 12, extra_w=20, height=34))
        self.btn_reset.clicked.connect(self.reset_app)
        toolbar.addWidget(self.btn_reset)

        width_lbl = QLabel("邮件宽度：")
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

        # ══ 第二行：导出模式 + 智能切图 + 复制HTML（右对齐） ═══
        toolbar2 = QHBoxLayout()
        toolbar2.setSpacing(10)

        # V4.7.7 Fix E: 导出模式 toggle（关闭=切图 / 打开=导出图片）
        # 替代 V4.6.2 拖入后弹 ProcessModeDialog 的体验，直接在面板切换。
        self.chk_export_mode = QCheckBox(" 导出图片")
        self.chk_export_mode.setFont(_font("Microsoft YaHei", 12))
        self.chk_export_mode.setChecked(False)  # 默认=切图模式（V4.6.1 行为）
        self.chk_export_mode.setCursor(Qt.PointingHandCursor)
        self.chk_export_mode.setToolTip(
            "关闭：拖入后进入切图模式（切成多片，发送 Outlook）\n"
            "打开：拖入后进入图片导出模式（合并/转换为单张长图）"
        )
        _chk_indicator_style = (
            f"QCheckBox {{ color: {Theme.TEXT_PRIMARY}; background: transparent; spacing: 6px; "
            f"font-weight: 500; }}"
            f"QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; "
            f"border: 1px solid {Theme.BORDER}; background: {Theme.CARD}; }}"
            f"QCheckBox::indicator:checked {{ background: {Theme.PRIMARY}; "
            f"border-color: {Theme.PRIMARY}; }}"
        )
        self.chk_export_mode.setStyleSheet(_chk_indicator_style)
        self.chk_export_mode.setIcon(_icon("image", 18))
        self.chk_export_mode.stateChanged.connect(self._on_export_mode_changed)
        toolbar2.addWidget(self.chk_export_mode)

        # V4.7.7 视觉分隔：mode 与 smart 之间用细线分开，避免视觉混淆
        sep_lbl = QLabel("│")
        sep_lbl.setFont(_font("Microsoft YaHei", 12))
        sep_lbl.setStyleSheet(f"color: {Theme.BORDER}; background: transparent; padding: 0 4px;")
        sep_lbl.setFixedWidth(12)
        toolbar2.addWidget(sep_lbl)

        self.chk_smart = QCheckBox("避开文字切图（推荐）")
        self.chk_smart.setFont(_font("Microsoft YaHei", 12))
        self.chk_smart.setChecked(True)  # 默认智能切图，优先避免切断文字
        self.chk_smart.setCursor(Qt.PointingHandCursor)
        self.chk_smart.setStyleSheet(_chk_indicator_style)
        toolbar2.addWidget(self.chk_smart)
        toolbar2.addStretch()
        root.addLayout(toolbar2)

        # 第三行只放处理完成后才会使用的动作，避免 760px 窗口横向挤压。
        toolbar3 = QHBoxLayout()
        toolbar3.setSpacing(10)

        self.btn_copy_html = QPushButton(" 复制到 Outlook")
        self.btn_copy_html.setFont(_font("Microsoft YaHei", 12))
        self.btn_copy_html.setCursor(Qt.PointingHandCursor)
        self.btn_copy_html.setEnabled(False)
        self.btn_copy_html.setStyleSheet(_btn_ghost())
        self.btn_copy_html.setIcon(_icon("clipboard-copy", 18))
        self.btn_copy_html.setIconSize(QSize(18, 18))
        self.btn_copy_html.setFixedSize(_btn_size(" 复制到 Outlook", 12, extra_w=20, height=34))
        self.btn_copy_html.clicked.connect(self._copy_html)
        toolbar3.addWidget(self.btn_copy_html)

        self.btn_adjust_cuts = QPushButton(" 调整切图位置")
        self.btn_adjust_cuts.setFont(_font("Microsoft YaHei", 12))
        self.btn_adjust_cuts.setCursor(Qt.PointingHandCursor)
        self.btn_adjust_cuts.setEnabled(False)
        self.btn_adjust_cuts.setStyleSheet(_btn_ghost())
        self.btn_adjust_cuts.setIcon(_icon("scissors", 18))
        self.btn_adjust_cuts.setIconSize(QSize(18, 18))
        self.btn_adjust_cuts.setFixedSize(
            _btn_size(" 调整切图位置", 12, extra_w=22, height=34)
        )
        self.btn_adjust_cuts.setToolTip(
            "切图完成后可拖动横线微调切开位置；自动限制在 Outlook 安全高度内"
        )
        self.btn_adjust_cuts.clicked.connect(self._adjust_cut_positions)
        toolbar3.addWidget(self.btn_adjust_cuts)

        self.btn_hotspot = QPushButton(" 添加可点击按钮")
        self.btn_hotspot.setFont(_font("Microsoft YaHei", 12))
        self.btn_hotspot.setCursor(Qt.PointingHandCursor)
        self.btn_hotspot.setEnabled(False)
        self.btn_hotspot.setStyleSheet(_btn_ghost())
        self.btn_hotspot.setIcon(_icon("mouse-pointer-click", 18))
        self.btn_hotspot.setIconSize(QSize(18, 18))
        self.btn_hotspot.setFixedSize(_btn_size(" 添加可点击按钮", 12, extra_w=20, height=34))
        self.btn_hotspot.setToolTip("在切片上框选按钮区域并添加链接")
        self.btn_hotspot.clicked.connect(self._open_hotspot_editor)
        self.btn_hotspot.setVisible(HOTSPOT_FEATURE_ENABLED)
        if HOTSPOT_FEATURE_ENABLED:
            toolbar3.addWidget(self.btn_hotspot)

        toolbar3.addStretch()
        root.addLayout(toolbar3)

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
        self.preview_area.setFixedHeight(160)
        self.preview_area.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {Theme.BORDER}; border-radius: 10px; "
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

        self.btn_send = QPushButton(" 在 Outlook 中创建邮件")
        self.btn_send.setFont(_font("Microsoft YaHei", 14, QFont.Bold))
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setEnabled(False)
        self.btn_send.setStyleSheet(_btn_primary())
        self.btn_send.setFixedHeight(44)
        self.btn_send.setIcon(_icon("mail", 20))
        self.btn_send.setIconSize(QSize(20, 20))
        self.btn_send.clicked.connect(self._send_email)

        self.btn_save = QPushButton(" 保存切图")
        self.btn_save.setFont(_font("Microsoft YaHei", 13, QFont.Medium))
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setEnabled(False)
        self.btn_save.setStyleSheet(_btn_secondary())
        self.btn_save.setFixedHeight(44)
        self.btn_save.setIcon(_icon("arrow-down-to-line", 18))
        self.btn_save.setIconSize(QSize(18, 18))
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
        self._set_status("拖入文件后自动切图，再检查切线并在经典 Outlook 中创建邮件", "info")

    # ── 工具函数 ────────────────────────────
    def _get_width(self) -> int:
        try:
            v = int(self.edit_width.text())
        except ValueError:
            return Config.DEFAULT_WIDTH
        v = max(400, min(1920, v))
        if v % 2 != 0:
            v -= 1
        return v

    def _set_status(self, text: str, level: str = "info"):
        icons = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️"}
        colors = {"info": Theme.TEXT_SECONDARY, "success": Theme.SUCCESS,
                  "error": Theme.ERROR, "warning": Theme.WARNING}
        clean = text.strip()
        prefixes = tuple(icons.values())
        while clean.startswith(prefixes):
            for prefix in prefixes:
                if clean.startswith(prefix):
                    clean = clean[len(prefix):].strip()
                    break
        self.status_label.setText(f"{icons.get(level, '')} {clean}".strip())
        self.status_label.setStyleSheet(
            f"color: {colors.get(level, Theme.TEXT_SECONDARY)}; "
            f"font-size: 12px; background: transparent; padding: 4px 0;"
        )

    def _reset_drop_zone(self):
        self.drop_zone.set_compact(False)
        self.drop_zone.title_label.setText("拖拽图片到此处")
        self.drop_zone.icon_label.setPixmap(_icon("upload-cloud", 44).pixmap(44, 44))
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
            if v % 2 != 0:
                v -= 1
            self.slider_width.blockSignals(True)
            self.slider_width.setValue(v)
            self.slider_width.blockSignals(False)
            self.edit_width.setText(str(v))
        except ValueError:
            self.edit_width.setText(str(self.slider_width.value()))

    def _on_slider_changed(self, value: int):
        """滑块拖动时同步到输入框"""
        if value % 2 != 0:
            value -= 1
            self.slider_width.blockSignals(True)
            self.slider_width.setValue(value)
            self.slider_width.blockSignals(False)
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

    def _on_export_mode_changed(self, state: int):
        """
        V4.7.7 Fix E: 切换模式时即时状态反馈。
        避免用户点完 toggle 不知道现在走哪个流程。
        """
        # state 是 Qt.CheckState 枚举的 int 值（非零=True）
        if bool(state):
            # 导出模式
            self._set_status(
                "导出图片模式：拖入文件后将合并/转换为单张长图保存到本地",
                "info"
            )
        else:
            # 切图模式（默认）
            self._set_status(
                "切图模式：拖入文件后将切成多片，可在面板添加可点击按钮后发送 Outlook",
                "info"
            )

    def _handle_dropped_files(self, paths: List[str]):
        """
        入口：处理一次拖入/选择的一批文件。
        V4.7.7 Fix E: 不再弹 ProcessModeDialog，根据面板 chk_export_mode 状态分流。
          - 关闭（默认）= 切图模式
          - 打开 = 图片导出模式
        """
        # 过滤合法后缀
        valid = [p for p in paths if Path(p).suffix.lower() in Config.SUPPORTED_EXTENSIONS]
        if not valid:
            QMessageBox.warning(self, "格式不支持", "请选择图片、PDF、PPT 或 PSD/PSB 文件。")
            return

        # V4.7.7 Fix E: 默认走自然排序（移除 V4.6.2 弹窗中的排序选项）
        def _natural_key(s):
            return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', Path(s).stem)]
        valid = sorted(valid, key=_natural_key)

        # V4.7.7 Fix E: 根据面板 toggle 状态分流
        is_export = self.chk_export_mode.isChecked()

        if is_export:
            # ── 导出模式：直接弹格式选择弹窗（合并/格式/路径） ──
            initial_export_dir = self.last_export_dir
            export_dlg = ExportFormatDialog(valid, self, initial_save_dir=initial_export_dir)
            if export_dlg.exec() != QDialog.Accepted:
                return
            er = export_dlg.get_result()
            self.last_export_dir = er["save_dir"]
            self._export_images(valid, save_dir=er["save_dir"],
                                fmt=er["format"], keep_alpha=er["keep_alpha"])
        else:
            # ── 切图模式：原 V4.6.1 路径（不再弹智能拼图弹窗） ──
            if len(valid) == 1:
                self._start_processing(valid[0])
            else:
                # V4.7.8 R4: 多图切图模式 → 状态栏提示 + 模态 QMessageBox 二次确认
                # 修复 R2 审查遗留第 4 个 UX 风险: "降级提示不够醒目"
                # 之前仅 _set_status 多行文本，用户可能没注意到直接关闭
                self._start_processing(valid[0])
                self._set_status(
                    f"💡 多图模式仅处理了第一张图片（共 {len(valid)} 张）。"
                    f"如需合并多图，请打开右上角「🖼️ 导出图片」开关后再拖入。",
                    "info"
                )
                # 模态提示：必须点确认才继续，避免用户错过
                QMessageBox.information(
                    self,
                    "🖼️ 多图模式提示",
                    f"已处理第一张图片（共 {len(valid)} 张）。\n\n"
                    f"💡 如需将多张图片合并为一张长图，请打开右上角\n"
                    f"   「🖼️ 导出图片」开关后再拖入文件。",
                )

    def _export_images(self, paths: List[str], save_dir: Optional[str] = None,
                       fmt: str = "png", keep_alpha: bool = True):
        """
        图片导出模式（V4.6.3 重写 + V4.7.6 架构升级）：
        - fmt: 'png' (支持透明) / 'jpg' (强制白底)
        - keep_alpha: 是否保留透明底（仅 png 有效）
        - 多图自动合并为长图，再按选定格式保存
        - V4.7.6: 支持 JPG/PNG/BMP/WEBP/GIF/PDF/PPT/PPTX/PSD/PSB 任意受支持格式
          (通过 _render_source_to_images 统一渲染成 PIL Image)
        """
        self._set_status("正在图片导出...", "info")
        try:
            from PIL import Image as PILImage
            # V4.7.6: 多页文件大数量确认
            from pathlib import Path
            _exts_multi = (".pdf", ".ppt", ".pptx", ".psd", ".psb")
            if any(Path(p).suffix.lower() in _exts_multi for p in paths):
                # 预估总页数（一次性扫一遍）
                total_pages = 0
                for p in paths:
                    try:
                        total_pages += len(_render_source_to_images(p))
                    except Exception:
                        pass
                if total_pages > 5:
                    reply = QMessageBox.question(
                        self, "多页文件确认",
                        f"检测到多页文件，总计约 {total_pages} 页。\n"
                        f"将合并为一张长图导出。是否继续？",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    if reply != QMessageBox.Yes:
                        self._set_status("已取消导出", "info")
                        return

            # 1) V4.7.6: 用 _render_source_to_images 统一渲染（替代旧 _PI.open 直开）
            images = []
            for p in paths:
                try:
                    rendered = _render_source_to_images(p)
                except Exception as e:
                    self._set_status(f"无法渲染 {Path(p).name}: {e}", "error")
                    return
                for img in rendered:
                    # PNG 保留透明底则保留 RGBA；否则转 RGB
                    if fmt == "png" and keep_alpha:
                        if img.mode != "RGBA":
                            img = img.convert("RGBA")
                    else:
                        # JPG 强制白底 / PNG 不保留透明
                        if img.mode in ("RGBA", "LA", "P"):
                            bg = PILImage.new("RGB", img.size, (255, 255, 255))
                            if img.mode in ("RGBA", "LA"):
                                bg.paste(img, mask=img.split()[-1])
                            else:
                                bg.paste(img.convert("RGB"))
                            img = bg
                        elif img.mode != "RGB":
                            img = img.convert("RGB")
                    images.append(img)

            # 2) 单图直接保存 / 多图合并
            if len(images) == 1:
                merged = images[0]
            else:
                # 多图：纵向拼接（保持原 RGBA/RGB）
                widths = [im.width for im in images]
                heights = [im.height for im in images]
                canvas_w = max(widths)
                canvas_h = sum(heights)
                # 按第一张图的 mode 决定画布 mode
                if images[0].mode == "RGBA":
                    canvas = PILImage.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                else:
                    canvas = PILImage.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
                y = 0
                for im in images:
                    x = (canvas_w - im.width) // 2
                    if im.mode == "RGBA" and canvas.mode == "RGBA":
                        canvas.alpha_composite(im, (x, y))
                    else:
                        canvas.paste(im, (x, y))
                    y += im.height
                merged = canvas

            # 3) 保存到目标路径
            if not save_dir:
                save_dir = QFileDialog.getExistingDirectory(
                    self, "选择保存目录", self.last_export_dir or ""
                )
                if not save_dir:
                    self._set_status("已取消导出", "info")
                    return
            self.last_export_dir = save_dir

            # V4.7.7 防御 1: 目录存在性 + 可写性检查
            if not os.path.isdir(save_dir):
                QMessageBox.critical(self, "导出失败", f"目录不存在：\n{save_dir}")
                self._set_status(f"❌ 目录不存在: {save_dir}", "error")
                return
            test_write = os.path.join(save_dir, ".outlook_slicer_write_test")
            try:
                with open(test_write, "w") as _tf:
                    _tf.write("test")
                os.remove(test_write)
            except Exception as _we:
                QMessageBox.critical(self, "导出失败",
                    f"目录无写权限：\n{save_dir}\n\n原因：{_we}\n\n"
                    f"请选择其他目录（如桌面、文档）。")
                self._set_status(f"❌ 目录无写权限: {save_dir}", "error")
                return

            ext = "png" if fmt == "png" else "jpg"
            # V4.7.7 修复：用 len(images) 不用 len(paths)
            # paths 是原始输入文件数，images 是渲染后图片数
            # 单文件多页（如 1 PDF 3 页）时 len(paths)=1, len(images)=3
            # V4.7.7 R2 架构师建议：完整时间戳 + pid 避免 1 秒内重名
            suffix = f"_{int(time.time())}_{os.getpid()}" if len(images) > 1 else ""
            base_name = "merged" if len(images) > 1 else Path(paths[0]).stem
            fname = f"{base_name}{suffix}.{ext}"
            dst = os.path.join(save_dir, fname)

            if fmt == "jpg":
                # JPG 不支持 RGBA → 强制转 RGB
                if merged.mode != "RGB":
                    bg = PILImage.new("RGB", merged.size, (255, 255, 255))
                    if merged.mode in ("RGBA", "LA"):
                        bg.paste(merged, mask=merged.split()[-1])
                    else:
                        bg.paste(merged.convert("RGB"))
                    merged = bg
                merged.save(dst, "JPEG", quality=95)
            else:
                # PNG：保留原 mode（RGBA 或 RGB）
                merged.save(dst, "PNG")

            # V4.7.7 防御 2: 保存后验证文件存在 + size > 0
            if not os.path.exists(dst):
                QMessageBox.critical(self, "导出失败", f"文件保存后未找到：\n{dst}\n请检查目录权限。")
                self._set_status(f"❌ 文件未生成: {dst}", "error")
                return
            file_size = os.path.getsize(dst)
            if file_size == 0:
                os.remove(dst)  # 清掉 0 字节文件
                QMessageBox.critical(self, "导出失败", f"文件保存为空 (0 字节)：\n{dst}")
                self._set_status(f"❌ 文件 0 字节: {dst}", "error")
                return

            # 成功：明确反馈
            file_count = 1
            page_info = f"({len(images)} 页合并)" if len(images) > 1 else ""
            QMessageBox.information(self, "导出成功",
                f"✅ 图片已导出至：\n{dst}\n\n"
                f"格式：{ext.upper()}\n"
                f"大小：{file_size:,} 字节 {page_info}\n"
                f"透明底：{'保留' if (fmt=='png' and keep_alpha) else '白底'}")
            self._set_status(f"✅ 图片已导出至：{dst} ({file_size:,} 字节)", "success")
            self.reset_app()
            self._set_status("✅ 导出完成，可继续拖入新图片", "success")
        except Exception as exc:
            # V4.7.7 防御 3: 详细错误反馈
            tb = traceback.format_exc()
            QMessageBox.critical(self, "导出失败",
                f"错误：{exc}\n\n"
                f"详细堆栈（请报错时截图）：\n{tb[:1500]}")
            self._set_status(f"❌ 导出失败: {exc}", "error")

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
        self.drop_zone.icon_label.setPixmap(_icon("check", 44).pixmap(44, 44))
        self.drop_zone.tip_label.setText("正在切片处理...")
        self._set_status("正在处理，请稍候...", "info")
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self._start_worker(path)

    def _start_worker(self, path: str):
        # V4.8.7: quit() + wait() 而非仅 deleteLater()，避免双线程并发
        if self.worker is not None:
            if self.worker.isRunning():
                self.worker.quit()
                if not self.worker.wait(2000):
                    # 兜底：2s 未结束则强制 terminate
                    self.worker.terminate()
                    self.worker.wait(1000)
            self.worker.deleteLater()
            self.worker = None
        self.worker = ProcessWorker(path, self._get_width(), smart=self.chk_smart.isChecked())
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._on_processed)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_processed(self, paths: List[str]):
        previous_paths = list(self.slice_paths)
        self.slice_paths = paths
        if previous_paths and set(previous_paths) != set(paths):
            cleanup_generated_slices(previous_paths)
        self.drop_zone.set_compact(bool(paths))
        if paths:
            self.drop_zone.tip_label.setText("处理完成；可重新拖入文件替换")
        # V4.6.7：按生成顺序填 source_index（原切片 = 1.0, 2.0, 3.0, ...）
        # 这里的“顺序”由 image_slicer.detect_and_slice 返回顺序决定
        # —— _build_slices_with_hotspots 会用本映射，未误用 path.index() 兑底
        self.slice_source_index = {
            os.path.basename(p): float(i + 1) for i, p in enumerate(paths)
        }
        # V4.6.9 修复：重新切图时必须清空 hotspot_map，
        # 避免旧图的 hotspot 污染新图（特别是新图上多点几次不同切片时）
        # 如果有残留 hotspot，发送时 hotspots_by_slice 会包含旧名，slice_paths 找不到
        # → 旧 hotspot 实际上不会起作用（B 的文件名查不到），但 hotspot_map 越变越乱
        self.hotspot_map.clear()
        self.progress_bar.hide()
        self.btn_send.setEnabled(bool(paths))
        self.btn_save.setEnabled(bool(paths))
        self.btn_copy_html.setEnabled(bool(paths))
        self.btn_hotspot.setEnabled(bool(paths) and HOTSPOT_FEATURE_ENABLED)
        self.btn_adjust_cuts.setEnabled(len(paths) > 1)

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
        """展示切片缩略图，V4.6.4 加角标 + 双行提示"""
        from PySide6.QtWidgets import QVBoxLayout, QWidget
        while self.thumb_grid.count():
            item = self.thumb_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        cols = 4
        for i, path in enumerate(paths):
            row, col = divmod(i, cols)
            # 每个缩略图用 QWidget 包裹：上面图，下面文字标识
            wrapper = QWidget()
            wrapper.setFixedSize(128, 130)
            if HOTSPOT_FEATURE_ENABLED:
                wrapper.setCursor(Qt.PointingHandCursor)
                wrapper.setToolTip(
                    f"切片 {i + 1}: {Path(path).name}\n"
                    f"点击可添加/编辑可点击按钮（热区）"
                )
                wrapper.setStyleSheet(
                    "QWidget { background: transparent; }"
                    "QWidget:hover { background: #e5e9ff; border-radius: 8px; }"
                )
            else:
                wrapper.setCursor(Qt.ArrowCursor)
                wrapper.setToolTip(f"切片 {i + 1}: {Path(path).name}")
                wrapper.setStyleSheet("QWidget { background: transparent; }")
            wrapper_layout = QVBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(4, 4, 4, 4)
            wrapper_layout.setSpacing(2)

            # 图片（V4.8.7: QPixmapCache 避免同一路径多次缩放）
            thumb = QLabel()
            thumb.setFixedSize(120, 100)
            thumb.setScaledContents(True)
            thumb.setStyleSheet(
                f"background: {Theme.CARD}; border-radius: 8px; border: 1px solid {Theme.BORDER};"
            )
            from PySide6.QtGui import QPixmapCache
            pix_key = f"thumb_{path}"
            pix = QPixmapCache.find(pix_key)
            if pix is None or pix.isNull():
                pix = QPixmap(path).scaled(120, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                QPixmapCache.insert(pix_key, pix)
            thumb.setPixmap(pix)
            wrapper_layout.addWidget(thumb)

            # 文字标识
            label = QLabel(f"#{i+1}" if not HOTSPOT_FEATURE_ENABLED else f"#{i+1} ✏️ 编辑热区")
            label.setFont(QFont("Microsoft YaHei", 9))
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                "color: #7f8d9f; background: transparent; padding: 2px;"
                if not HOTSPOT_FEATURE_ENABLED
                else "color: #0065fd; background: transparent; padding: 2px;"
            )
            wrapper_layout.addWidget(label)

            # 点击缩略图即可为该切片添加/编辑可点击按钮。
            if HOTSPOT_FEATURE_ENABLED:
                wrapper.mousePressEvent = lambda ev, p=path, idx=i: self._on_thumb_clicked(ev, p, idx)
            self.thumb_grid.addWidget(wrapper, row, col)
        self.preview_area.show()
        # V4.6.4：状态条提示缩略图可点
        if paths and HOTSPOT_FEATURE_ENABLED:
            self._set_status(
                f"已生成 {len(paths)} 张切片 — 点击下方任一缩略图可添加可点击热区",
                "info",
            )

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

    def _build_slices_with_hotspots(self) -> List[SliceItem]:
        """
        V4.6.6 V1 + V4.6.7 排序架构：根据 hotspot_map 物理切割切片，生成 List[SliceItem]。

        每项是 (path, href, sort_key)：
          - href=None: 普通切片 → <img>
          - href=str:  链接切片 → <a href><img></a>
          - sort_key: V4.6.7 排序架构唯一依据，html_assembler 会按它排序
        """
        if not self.slice_paths:
            return []
        from pathlib import Path
        # hotspot_map 按切片名分组
        hotspots_by_slice: Dict[str, List[Hotspot]] = {}
        for fname in self.hotspot_map.all_slices():
            hotspots_by_slice[fname] = self.hotspot_map.get(fname)
        # V4.6.7：传 source_index_map 避免 hotspot_slicer 兜底按 path.index() 隐式顺序
        slices_with_key, link_map = slice_paths_by_hotspots(
            self.slice_paths, hotspots_by_slice, source_index_map=self.slice_source_index
        )
        # V4.6.9 修复：记录每张切片的"原图宽度"，用于 HTML 多段拼接按比例缩放
        # 同一 source_index 的所有 hotspot 派生切片属于同一张原图
        # 同一原图的所有切片（包括原切片 + 派生切片）共享 original_width = 原图 w
        # 这里用 source_index_map 即可找到原图（它存的是"原切片 → source_index"）
        # 反向：source_index → 原切片路径
        from PIL import Image as _PIL_Image
        si_to_orig: Dict[float, str] = {}
        for fname, si in self.slice_source_index.items():
            si_to_orig[si] = os.path.join(os.path.dirname(self.slice_paths[0]) if self.slice_paths else '.', fname)
        # 缓存原图宽
        orig_w_cache: Dict[str, int] = {}

        items: List[SliceItem] = []
        for p, sk in slices_with_key:
            name = Path(p).name
            hs_list = self.hotspot_map.get(name)
            alt_text = hs_list[0].text if hs_list and hs_list[0].text else ""
            # V4.6.9：找原图（sort_key 的整数部分 = source_index）
            source_idx = int(sk)  # 1, 2, 3, ...
            orig_path = si_to_orig.get(float(source_idx), '')
            if orig_path and orig_path not in orig_w_cache:
                try:
                    with _PIL_Image.open(orig_path) as im:
                        orig_w_cache[orig_path] = im.size[0]
                except Exception:
                    orig_w_cache[orig_path] = 0
            orig_w = orig_w_cache.get(orig_path, 0)
            items.append(SliceItem(
                path=p,
                href=link_map.get(name),
                alt_text=alt_text,
                sort_key=sk,
                original_width=orig_w,
            ))
        return items

    def _copy_html(self):
        """复制 HTML 到剪贴板（同时写入 HTML 和纯文本格式）"""
        if not self.slice_paths:
            return
        # V4.8.7: 记录 materialize 临时文件，复制成功后清理
        temp_files: List[str] = []
        try:
            display_w = self._get_width()
            from html_assembler import _materialized_temp_files
            tracked_before = len(_materialized_temp_files)
            html = generate_plain_html(
                self._build_slices_with_hotspots(), display_w
            )
            # 只清理本次 generate_plain_html 新登记的文件。不能 glob 系统临时目录，
            # 否则会误删另一个应用实例仍在使用的 mail_*.png。
            temp_files = list(_materialized_temp_files[tracked_before:])

            mime = QMimeData()
            mime.setHtml(html)
            mime.setData("HTML Format", _build_windows_clipboard_html(html))
            mime.setText(html)
            QGuiApplication.clipboard().setMimeData(mime)
            self._set_status("HTML 已复制（适用于 Gmail / 网页邮箱；Outlook 桌面版请改用『创建 Outlook 草稿』）", "success")
            # V4.8.7: 已复制到剪贴板（base64 内嵌），清理临时文件
            deleted = cleanup_temp_slices(temp_files)
            if deleted:
                self._set_status(f"HTML 已复制（已清理 {deleted} 个临时文件）", "success")
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
            with Image.open(p) as img:
                if img.mode in ("RGBA", "LA"):
                    rgb = Image.new("RGB", img.size, (255, 255, 255))
                    rgb.paste(img, mask=img.split()[-1])
                elif img.mode == "P":
                    rgb = img.convert("RGB")
                else:
                    rgb = img.convert("RGB") if img.mode != "RGB" else img.copy()
            new_path = str(Path(p).with_suffix(".jpg"))
            rgb.save(new_path, format="JPEG", quality=COMPRESS_QUALITY, optimize=True)
            self.slice_paths[i] = new_path

    def _compress_slice_items(self, slices: List[SliceItem]) -> List[SliceItem]:
        """
        压缩最终发送用 SliceItem，保留 href / sort_key / alt_text。

        不能先压缩 self.slice_paths：热区数据按原始切片文件名保存，先把
        slice_001.png 改成 slice_001.jpg 会导致发送路径中热点匹配丢失。
        """
        if not slices:
            return []
        from PIL import Image

        compressed: List[SliceItem] = []
        for idx, item in enumerate(slices, start=1):
            src = Path(item.path)
            dst = src.with_name(f"{src.stem}_q{COMPRESS_QUALITY}_{idx:03d}.jpg")
            with Image.open(item.path) as img:
                if img.mode in ("RGBA", "LA"):
                    rgb = Image.new("RGB", img.size, (255, 255, 255))
                    rgb.paste(img, mask=img.split()[-1])
                elif img.mode == "P":
                    rgb = img.convert("RGB")
                else:
                    rgb = img.convert("RGB") if img.mode != "RGB" else img.copy()
            rgb.save(dst, format="JPEG", quality=COMPRESS_QUALITY, optimize=True)
            compressed.append(SliceItem(
                path=str(dst),
                href=item.href,
                alt_text=item.alt_text,
                sort_key=item.sort_key,
                original_width=item.original_width,
            ))
        return compressed

    def _send_email(self):
        if not self.slice_paths:
            return

        # V4.8.7: 记录 materialize 产生的临时文件，发送成功后清理
        # （失败时保留以供调试，正常路径下用户无感知）
        temp_files: List[str] = []
        try:
            display_w = self._get_width()
            raw_slices = self._build_slices_with_hotspots()

            # V4.9.3: 普通链路（无 hotspot、无 href）跳过 materialize，
            # 直接使用原始切片，完全对齐 V3.0 无缝行为。
            # materialize 会将宽度 650→652（4 的倍数归一化）并向上取整高度，
            # 这两个操作改变了 PNG 物理尺寸，是 V4.9.2 仍有缝隙的根因。
            groups = _group_by_source(sorted(raw_slices, key=lambda s: s.sort_key))
            is_plain = _is_plain_vertical_stack(groups)

            if is_plain:
                # 普通链路：不 materialize，直接用原始切片
                slices = raw_slices
            else:
                # hotspot/复杂链路：保留 materialize 预渲染
                slices = materialize_display_slices_strict(raw_slices, display_w)
                temp_files = [s.path for s in slices]

            # 体积检测基于最终发送切片，包含 hotspot 物理切割和预渲染后的真实文件。
            size_mb = estimate_email_size_mb([s.path for s in slices])
            if size_mb > MAX_EMAIL_SIZE_MB:
                btn_box = QMessageBox(self)
                btn_box.setWindowTitle("邮件体积较大")
                btn_box.setIcon(QMessageBox.Warning)
                btn_box.setText(f"预计 {size_mb}MB，超过推荐限制（{MAX_EMAIL_SIZE_MB}MB）")
                btn_box.setInformativeText(
                    f"<b>压缩后</b> 缩小至约 {COMPRESS_QUALITY}% 品质（推荐）\n"
                    f"<b>原画质</b> 保持当前品质直接发送"
                )
                btn_compress = btn_box.addButton(f" 压缩至 {COMPRESS_QUALITY}%", QMessageBox.AcceptRole)
                btn_compress.setIcon(_icon("arrow-down-to-line", 18))
                btn_compress.setIconSize(QSize(18, 18))
                btn_quality = btn_box.addButton(" 原画质发送", QMessageBox.NoRole)
                btn_quality.setIcon(_icon("palette", 18))
                btn_quality.setIconSize(QSize(18, 18))
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
                    slices = self._compress_slice_items(slices)
                    compressed_size = estimate_email_size_mb([s.path for s in slices])
                    self._set_status(
                        f"已压缩至约 {compressed_size}MB，正在打开邮件...",
                        "success"
                    )

            html_content = assemble_html(slices, display_w)
            subject = self.input_subject.text().strip() or "长图邮件"
            # V4.6.7：传 slices 让 outlook_sender 按 sort_key 排序后取 path
            # image_paths 保留向后兼容
            create_email_with_images(
                html_content, subject=subject, to="",
                slices=slices,
                image_paths=[s.path for s in slices]
            )
            self._set_status("邮件窗口已打开，请检查后发送", "success")
            # V4.8.7: Outlook 已收到 CID 附件，本地临时 PNG 可清理
            deleted = cleanup_temp_slices(temp_files)
            if deleted:
                self._set_status(f"邮件窗口已打开（已清理 {deleted} 个临时文件）", "success")
        except Exception as exc:
            QMessageBox.critical(self, "发送失败", str(exc))

    def reset_app(self):
        cleanup_generated_slices(self.slice_paths)
        self.slice_paths = []
        # V4.6.7 修复：重置时同步清空 source_index 映射，避免残留
        self.slice_source_index = {}
        self.file_path = None
        # V4.8.7: quit() + wait() 而非仅 deleteLater()，避免双线程并发
        if self.worker is not None:
            if self.worker.isRunning():
                self.worker.quit()
                if not self.worker.wait(2000):
                    self.worker.terminate()
                    self.worker.wait(1000)
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
        self.btn_adjust_cuts.setEnabled(False)
        self._set_status("拖入文件后自动切图，再检查切线并在经典 Outlook 中创建邮件", "info")

    def _adjust_cut_positions(self):
        """打开可视化切线编辑器，并在应用前执行安全与热区防呆检查。"""
        if len(self.slice_paths) < 2:
            QMessageBox.information(
                self,
                "无需调整",
                "当前只有一张切片，没有可移动的切线。",
            )
            return

        try:
            dialog = CutEditorDialog(
                self.slice_paths,
                max_slice_height=OUTLOOK_SAFE_MAX_HEIGHT_PER_SLICE,
                parent=self,
            )
        except Exception as exc:
            QMessageBox.critical(self, "无法打开切线编辑器", str(exc))
            return

        if dialog.exec() != QDialog.Accepted:
            return

        if not self.hotspot_map.is_empty():
            reply = QMessageBox.warning(
                self,
                "需要重新添加链接",
                "调整切图位置会改变图片坐标，现有可点击按钮将被清空。\n\n"
                "是否继续应用新的切线？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        try:
            new_paths = reslice_existing_stack(
                self.slice_paths,
                dialog.get_cut_positions(),
                min_height=CutEditorDialog.MIN_SLICE_HEIGHT,
                max_height=OUTLOOK_SAFE_MAX_HEIGHT_PER_SLICE,
            )
            self._on_processed(new_paths)
            self._set_status(
                f"已应用手动切线，共 {len(new_paths)} 张；请重新检查链接区域",
                "success",
            )
        except Exception as exc:
            QMessageBox.critical(self, "调整切图失败", str(exc))

    def _on_thumb_clicked(self, ev, path: str, idx: int):
        """点击缩略图 → 打开热区编辑器"""
        # V4.8.7: accept() 阻止 PySide 把这个 mousePress 当作"准备拖出"启动 DnD
        ev.accept()
        if not HOTSPOT_FEATURE_ENABLED:
            return
        if ev.button() == Qt.LeftButton:
            self._open_hotspot_editor_for_slice(path)

    def _open_hotspot_editor(self):
        """「添加可点击按钮」按钮 → 弹出切片选择 + 打开编辑器"""
        if not HOTSPOT_FEATURE_ENABLED:
            self._set_status("可点击按钮功能已临时隐藏：优先修复 Outlook 切图拼接缝问题", "warning")
            return
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
        dlg = HotspotEditorDialog(slice_path, self.hotspot_map, self, source_index=self.slice_source_index.get(os.path.basename(slice_path), 0.0))
        dlg.exec()
        # V4.6.6 V1：热区已标注，将在发送/复制时按 hotspot 纵向切割
        if not self.hotspot_map.is_empty():
            self._set_status(
                f"已为 {len(self.hotspot_map.all_slices())} 个切片添加共 "
                f"{self.hotspot_map.total_count()} 个可点击按钮 "
                f"（V1：发送时按 hotspot 物理切割，原图上无任何标注）",
                "success",
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(_font())
    # V5.0.3 修复：设置窗口图标（任务栏 + 标题栏）
    _app_icon_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "icon.ico"
    )
    if os.path.exists(_app_icon_path):
        app.setWindowIcon(QIcon(_app_icon_path))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
