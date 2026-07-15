"""
Outlook 长图助手 - 桌面主程序
PySide6 窗口应用，支持拖拽上传、自动切片、邮件体积检测、一键复制HTML、多图合并
"""
import os
import sys
import re
import time
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List, Dict

os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

# Direct source launches use desktop/ as sys.path[0]. Add the project root so
# the documented `python desktop/main.py` entrypoint can import core modules.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QProgressBar, QMessageBox, QFileDialog,
    QFrame, QGridLayout, QScrollArea,
    QLineEdit, QCheckBox, QDialog, QSizePolicy, QComboBox, QLayout
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QMimeData
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QFont, QFontDatabase, QFontMetrics, QKeyEvent, QGuiApplication, QIntValidator, QIcon

from theme import Theme, fit_window_to_screen

from image_slicer import (
    detect_and_slice,
    get_image_info,
    reslice_existing_stack,
    cleanup_generated_slices,
)
# image_slicer.auto_merge_images 函数本身保留以备未来使用
from pdf_slicer import pdf_to_images
from ppt_slicer import pptx_to_images
# psd_slicer 依赖 psd_tools + numpy，仅在用户上传 .psd 时懒加载，避免主程序启动报错
# from psd_slicer import psd_to_images
from clickable_map import HotspotMap, Hotspot
from hotspot_editor import HotspotEditorDialog
from html_assembler import (
    assemble_html, generate_plain_html, materialize_display_slices_strict,
    SliceItem, cleanup_temp_slices, build_render_plan,
    _group_by_source, _is_plain_vertical_stack,
)
from hotspot_slicer import slice_paths_by_hotspots
from outlook_sender import copy_cf_html_to_clipboard, create_email_with_images
from image_safety import check_image_safety, ImageSafetyError, estimate_email_size_mb
# 模式选择在主面板中完成，不再弹出单独模式选择窗口。
from export_dialog import ExportFormatDialog, FMT_PNG, FMT_JPG
from export_worker import ExportWorker
from clipboard_html import (
    build_windows_clipboard_html as _build_windows_clipboard_html,
)
from cut_editor import CutEditorDialog
import os

# ── 图标加载 ────────────────────────────────
def _resource_dir(name: str) -> str:
    """Resolve bundled resources in both source and PyInstaller onefile modes."""
    bases = [
        getattr(sys, "_MEIPASS", None),
        os.path.dirname(os.path.abspath(__file__)),
        os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")),
    ]
    for base in bases:
        if not base:
            continue
        candidate = os.path.join(base, name)
        if os.path.isdir(candidate):
            return candidate
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def _resource_file(name: str) -> str:
    """Resolve a bundled single file in source and PyInstaller onefile modes."""
    bases = [
        getattr(sys, "_MEIPASS", None),
        os.path.dirname(os.path.abspath(__file__)),
        os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")),
    ]
    for base in bases:
        if not base:
            continue
        candidate = os.path.join(base, name)
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def _set_test_id(widget, name: str, description: str = ""):
    widget.setObjectName(name)
    widget.setAccessibleName(name)
    if description:
        widget.setAccessibleDescription(description)


_ICONS_DIR = _resource_dir("icons")

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


VERSION = "6.3.0"
VERSION_BY = "xiaoming"
# 桌面版：PySide6 + 本地图像处理 + Outlook COM。
HOTSPOT_FEATURE_ENABLED = True
OUTLOOK_SAFE_MAX_HEIGHT_PER_SLICE = 1200
MAX_EMAIL_SIZE_MB = 20
COMPRESS_QUALITY = 65  # 压缩时 JPEG 质量


class Config:
    APP_TITLE = f"Outlook 长图助手 V{VERSION}"
    DEFAULT_WIDTH = 960
    MAX_HEIGHT_PER_SLICE = OUTLOOK_SAFE_MAX_HEIGHT_PER_SLICE
    MAX_SLICE_COUNT = 20
    WINDOW_WIDTH = 760
    WINDOW_HEIGHT = 720
    SUPPORTED_EXTENSIONS = (
        ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif",
        ".pdf", ".pptx", ".ppt", ".psd", ".psb"
    )


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


_ACTIVE_UI_SCALE = 1.0
_FONT_FAMILY: Optional[str] = None


def _preferred_font_family() -> str:
    global _FONT_FAMILY
    if _FONT_FAMILY:
        return _FONT_FAMILY
    available = set(QFontDatabase.families())
    for candidate in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Noto Sans CJK SC"):
        if candidate in available:
            _FONT_FAMILY = candidate
            break
    if not _FONT_FAMILY:
        _FONT_FAMILY = QApplication.font().family()
    return _FONT_FAMILY


def _font(family: str = "Microsoft YaHei UI", size: int = 12, weight: int = QFont.Normal) -> QFont:
    font = QFont(_preferred_font_family())
    font.setWeight(weight)
    font.setPointSizeF(max(1.0, size * _ACTIVE_UI_SCALE))
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
    )
    font.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
    return font


class WorkflowStep(QFrame):
    """A responsive section in the single-page three-step workflow."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.setObjectName("workflowStep")
        self.setStyleSheet(
            f"QFrame#workflowStep {{ background: {Theme.BG}; border: 1px solid {Theme.BORDER}; "
            "border-radius: 12px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        label = QLabel(title)
        label.setFont(_font("Microsoft YaHei", 11, QFont.Bold))
        label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; border: 0; background: transparent;")
        layout.addWidget(label)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        layout.addLayout(self.body)


def _btn_size(text: str, font_size: int = 13, extra_w: int = 36, height: int = 38) -> QSize:
    fm = QFontMetrics(QFont("Microsoft YaHei", font_size))
    return QSize(fm.horizontalAdvance(text) + extra_w, height)


def _btn_primary() -> str:
    return (
        f"QPushButton {{ background: {Theme.PRIMARY}; color: {Theme.PRIMARY_TEXT}; "
        f"border: none; border-radius: 21px; padding: 0 18px; font-weight: 700;}}"
        f"QPushButton:hover {{ background: {Theme.PRIMARY_HOVER}; }}"
        f"QPushButton:pressed {{ background: {Theme.PRIMARY_ACTIVE}; }}"
        f"QPushButton:disabled {{ background: {Theme.PRIMARY_DISABLED}; color: {Theme.TEXT_PLACEHOLDER}; }}"
    )


def _btn_secondary() -> str:
    return (
        f"QPushButton {{ background: {Theme.SECONDARY_BG}; color: {Theme.SECONDARY_TEXT}; "
        f"border: 1px solid {Theme.SECONDARY_BORDER}; border-radius: 21px; padding: 0 16px;}}"
        f"QPushButton:hover {{ background: {Theme.SECONDARY_HOVER}; border-color: {Theme.BORDER_HOVER}; }}"
        f"QPushButton:disabled {{ color: {Theme.TEXT_DISABLED}; border-color: {Theme.BORDER}; }}"
    )


def _btn_ghost() -> str:
    return (
        f"QPushButton {{ background: {Theme.GHOST_BG}; color: {Theme.GHOST_TEXT}; "
        f"border: none; border-radius: 16px; padding: 0 12px;}}"
        f"QPushButton:hover {{ background: {Theme.GHOST_HOVER}; }}"
        f"QPushButton:disabled {{ opacity: 0.5; }}"
    )


def _input_style() -> str:
    return (
        f"QLineEdit {{ background: {Theme.CARD}; color: {Theme.TEXT_PRIMARY}; "
        f"border: 1px solid {Theme.BORDER}; border-radius: 8px; "
        f"padding: 0 12px;}}"
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
        self._compact = False
        self._ui_scale = 1.0
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self):
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(28, 32, 28, 32)
        self.content_layout.setSpacing(10)
        self.content_layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setPixmap(_icon("upload-cloud", 56).pixmap(56, 56))
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        self.title_label = QLabel("拖拽图片到此处")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setFont(_font("Microsoft YaHei", 14, QFont.Bold))
        self.title_label.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent; border: none;")
        self.tip_label = QLabel("支持 JPG · PNG · BMP · WebP · GIF · PDF · PPT/PPTX · PSD/PSB，点击上传")
        self.tip_label.setAlignment(Qt.AlignCenter)
        self.tip_label.setWordWrap(True)
        self.tip_label.setFont(_font("Microsoft YaHei", 12))
        self.tip_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent; border: none;")

        self.content_layout.addWidget(self.icon_label)
        self.content_layout.addWidget(self.title_label)
        self.content_layout.addWidget(self.tip_label)
        self.setMinimumHeight(180)

    def set_compact(self, compact: bool):
        """Collapse the large drop target after processing so previews stay visible."""
        self._compact = compact
        self.apply_ui_scale(self._ui_scale)

    def apply_ui_scale(self, scale: float):
        self._ui_scale = scale
        px = lambda value: max(1, round(value * scale))
        compact = self._compact
        if compact:
            self.icon_label.hide()
            self.tip_label.hide()
            self.content_layout.setContentsMargins(px(16), px(7), px(16), px(7))
            self.content_layout.setSpacing(px(2))
            self.setMinimumHeight(px(48))
            self.setMaximumHeight(px(48))
        else:
            self.icon_label.show()
            self.tip_label.show()
            icon_size = px(56)
            self.icon_label.setPixmap(_icon("upload-cloud", icon_size).pixmap(icon_size, icon_size))
            self.content_layout.setContentsMargins(px(28), px(32), px(28), px(32))
            self.content_layout.setSpacing(px(10))
            self.setMinimumHeight(px(180))
            self.setMaximumHeight(16777215)
        self._apply_style()

    def _apply_style(self):
        border = Theme.DROPZONE_HOVER_BORDER if self._hovered else Theme.DROPZONE_IDLE_BORDER
        bg = Theme.DROPZONE_HOVER_BG if self._hovered else Theme.CARD
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border: {max(1, round(2 * self._ui_scale))}px dashed {border}; "
            f"border-radius: {max(1, round(12 * self._ui_scale))}px; }}"
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
                if self.isInterruptionRequested():
                    return []
                path = os.path.join(work_dir, f"{prefix}_{index}.png")
                image.save(path)
                slice_paths.append(path)
                # 释放 PIL Image 引用，避免百页大文件内存峰值
                del image
            self.progress.emit(p_after)
            final = []
            for p in slice_paths:
                if self.isInterruptionRequested():
                    cleanup_generated_slices(final)
                    return []
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
            if self.isInterruptionRequested():
                return
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
            if self.isInterruptionRequested():
                cleanup_generated_slices(slice_paths)
                return
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
        global _ACTIVE_UI_SCALE
        _ACTIVE_UI_SCALE = 1.0
        self._ui_scale = 1.0
        self._scale_baseline_ready = False
        self._applying_ui_scale = False
        self._thumbnail_signature = None
        self._status_level = "info"
        self.slice_paths: List[str] = []
        # V4.6.7 排序架构：原切片的 source_index 映射
        # key = slice 文件名，value = source_index（浮点：原切片=整数，Hotspot派生=整数+N*0.001）
        # **不依赖** slice_paths 顺序、文件名、目录遍历
        self.slice_source_index: Dict[str, float] = {}
        self.worker: Optional[ProcessWorker] = None
        self._retired_workers: List[ProcessWorker] = []
        self._active_job_id = 0
        self.hotspot_map = HotspotMap()
        self.last_export_dir: Optional[str] = None
        self._export_worker: Optional[ExportWorker] = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle(Config.APP_TITLE)
        fit_window_to_screen(self, (Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT), (620, 360))

        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.page_scroll.setStyleSheet(
            f"QScrollArea {{ background: {Theme.CARD}; border: 0; }}"
            f"QScrollArea > QWidget > QWidget {{ background: {Theme.CARD}; }}"
        )
        container = QWidget()
        container.setStyleSheet(f"background: {Theme.CARD};")
        self.page_scroll.setWidget(container)
        self.setCentralWidget(self.page_scroll)
        root = QVBoxLayout(container)
        root.setSizeConstraint(QVBoxLayout.SetMinimumSize)
        root.setContentsMargins(20, 16, 20, 14)
        root.setSpacing(8)

        # ══ Header ════════════════════════════
        self.header_title = QLabel(f"Outlook 长图助手 V{VERSION}")
        self.header_title.setFont(_font("Microsoft YaHei", 18, QFont.Bold))
        self.header_title.setMinimumHeight(30)
        self.header_title.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        root.addWidget(self.header_title)

        self.header_subtitle = QLabel("长图/PDF/PPT切片后插入Outlook邮件，保持原始清晰度")
        self.header_subtitle.setFont(_font("Microsoft YaHei", 11))
        self.header_subtitle.setMinimumHeight(22)
        self.header_subtitle.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        root.addWidget(self.header_subtitle)

        self.guide_label = QLabel(
            "1  放入文件    →    2  调整切线 / 添加链接    →    3  创建邮件"
        )
        self.guide_label.setFont(_font("Microsoft YaHei", 10, QFont.Medium))
        self.guide_label.setStyleSheet(
            f"color: {Theme.TEXT_SECONDARY}; background: {Theme.GHOST_BG}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 17px; "
            f"padding: 6px 10px;"
        )
        self.guide_label.setAlignment(Qt.AlignCenter)
        self.guide_label.setWordWrap(True)
        self.guide_label.setMinimumHeight(34)
        root.addWidget(self.guide_label)

        self.step_import = WorkflowStep("1  放入文件")
        root.addWidget(self.step_import)

        # ══ Drop Zone ════════════════════════
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._handle_dropped_files)
        self.drop_zone.clicked.connect(self._select_file)
        self.step_import.body.addWidget(self.drop_zone)

        # ══ 工具栏第一行：重置 + 宽度设置 + 复选框 ═══
        self.settings_container = QWidget()
        settings_layout = QHBoxLayout(self.settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(8)

        self.btn_reset = QPushButton("重置")
        self.btn_reset.setFont(_font("Microsoft YaHei", 11))
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet(_btn_ghost())
        self.btn_reset.setIcon(_icon("rotate-ccw", 16))
        self.btn_reset.setIconSize(QSize(16, 16))
        self.btn_reset.setMinimumHeight(32)
        self.btn_reset.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.btn_reset.clicked.connect(self.reset_app)
        _set_test_id(self.btn_reset, "resetButton")
        settings_layout.addWidget(self.btn_reset)

        width_lbl = QLabel("邮件宽度：")
        width_lbl.setFont(_font("Microsoft YaHei", 11))
        width_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")

        self.edit_width = QLineEdit(f"{Config.DEFAULT_WIDTH}")
        self.edit_width.setFont(_font("Microsoft YaHei", 11))
        self.edit_width.setValidator(QIntValidator(400, 1920))
        self.edit_width.setMinimumWidth(70)
        self.edit_width.setMaximumWidth(90)
        self.edit_width.setFixedHeight(32)
        self.edit_width.setAlignment(Qt.AlignCenter)
        self.edit_width.setStyleSheet(
            f"QLineEdit {{ background: {Theme.CARD}; color: {Theme.TEXT_PRIMARY}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 8px; "
            f"padding: 0 8px; }}"
            f"QLineEdit:focus {{ border-color: {Theme.BORDER_FOCUS}; }}"
        )
        self.edit_width.editingFinished.connect(self._on_width_edited)
        _set_test_id(self.edit_width, "mailWidthInput", "邮件正文图片显示宽度，单位像素")
        px_lbl = QLabel("px")
        px_lbl.setFont(_font("Microsoft YaHei", 11))
        px_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        width_control = QWidget()
        width_layout = QHBoxLayout(width_control)
        width_layout.setContentsMargins(0, 0, 0, 0)
        width_layout.setSpacing(5)
        width_layout.addWidget(width_lbl)
        width_layout.addWidget(self.edit_width)
        width_layout.addWidget(px_lbl)
        settings_layout.addWidget(width_control)

        # 分隔符
        sep_label = QLabel("│")
        sep_label.setFont(_font("Microsoft YaHei", 11))
        sep_label.setStyleSheet(f"color: {Theme.BORDER}; background: transparent;")
        settings_layout.addWidget(sep_label)

        # 功能选项复选框（并入第一行，与宽度输入同排）
        _chk_indicator_style = (
            f"QCheckBox {{ color: {Theme.TEXT_PRIMARY}; background: transparent; spacing: 6px; "
            f"font-weight: 500;}}"
            f"QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; "
            f"border: 1px solid {Theme.BORDER}; background: {Theme.CARD}; }}"
            f"QCheckBox::indicator:checked {{ background: {Theme.PRIMARY}; "
            f"border-color: {Theme.PRIMARY}; }}"
        )

        self.chk_export_mode = QCheckBox("导出图片")
        self.chk_export_mode.setFont(_font("Microsoft YaHei", 11))
        self.chk_export_mode.setChecked(False)
        self.chk_export_mode.setCursor(Qt.PointingHandCursor)
        self.chk_export_mode.setToolTip(
            "关闭：拖入后进入切图模式（切成多片，发送 Outlook）\n"
            "打开：拖入后进入图片导出模式（合并/转换为单张长图）"
        )
        self.chk_export_mode.setStyleSheet(_chk_indicator_style)
        self.chk_export_mode.setIcon(_icon("image", 16))
        self.chk_export_mode.setIconSize(QSize(16, 16))
        self.chk_export_mode.stateChanged.connect(self._on_export_mode_changed)
        _set_test_id(self.chk_export_mode, "mergeExportModeCheckbox")
        settings_layout.addWidget(self.chk_export_mode)

        self.chk_smart = QCheckBox("避开文字切图（推荐）")
        self.chk_smart.setFont(_font("Microsoft YaHei", 11))
        self.chk_smart.setChecked(True)
        self.chk_smart.setCursor(Qt.PointingHandCursor)
        self.chk_smart.setStyleSheet(_chk_indicator_style)
        _set_test_id(self.chk_smart, "smartSliceCheckbox")
        settings_layout.addWidget(self.chk_smart)

        settings_layout.addStretch()
        self.step_import.body.addWidget(self.settings_container)

        self.step_edit = WorkflowStep("2  编辑切片与链接")
        root.addWidget(self.step_edit, stretch=1)

        # ══ 工具栏第三行：处理完成后的动作按钮（可换行布局）═══
        self.edit_actions_container = QWidget()
        self.edit_actions_grid = QGridLayout(self.edit_actions_container)
        self.edit_actions_grid.setContentsMargins(0, 0, 0, 0)
        self.edit_actions_grid.setSpacing(8)

        self.btn_copy_html = QPushButton("复制图片（兼容方式）")
        self.btn_copy_html.setFont(_font("Microsoft YaHei", 11))
        self.btn_copy_html.setCursor(Qt.PointingHandCursor)
        self.btn_copy_html.setEnabled(False)
        self.btn_copy_html.setStyleSheet(_btn_ghost())
        self.btn_copy_html.setIcon(_icon("clipboard-copy", 16))
        self.btn_copy_html.setIconSize(QSize(16, 16))
        self.btn_copy_html.setMinimumHeight(32)
        self.btn_copy_html.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.btn_copy_html.clicked.connect(self._copy_html)
        self.btn_copy_html.setToolTip("手动粘贴到邮件；链接兼容性低于“在 Outlook 中创建邮件”")
        _set_test_id(self.btn_copy_html, "copyCompatibilityButton")

        self.btn_adjust_cuts = QPushButton("调整切图位置")
        self.btn_adjust_cuts.setFont(_font("Microsoft YaHei", 11))
        self.btn_adjust_cuts.setCursor(Qt.PointingHandCursor)
        self.btn_adjust_cuts.setEnabled(False)
        self.btn_adjust_cuts.setStyleSheet(_btn_ghost())
        self.btn_adjust_cuts.setIcon(_icon("scissors", 16))
        self.btn_adjust_cuts.setIconSize(QSize(16, 16))
        self.btn_adjust_cuts.setMinimumHeight(32)
        self.btn_adjust_cuts.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.btn_adjust_cuts.setToolTip(
            "切图完成后可自由拖动横线；超长区间会自动补充 Outlook 安全切线"
        )
        self.btn_adjust_cuts.clicked.connect(self._adjust_cut_positions)
        _set_test_id(self.btn_adjust_cuts, "adjustCutsButton")

        self.btn_hotspot = QPushButton("添加可点击按钮")
        self.btn_hotspot.setFont(_font("Microsoft YaHei", 11))
        self.btn_hotspot.setCursor(Qt.PointingHandCursor)
        self.btn_hotspot.setEnabled(False)
        self.btn_hotspot.setStyleSheet(_btn_ghost())
        self.btn_hotspot.setIcon(_icon("mouse-pointer-click", 16))
        self.btn_hotspot.setIconSize(QSize(16, 16))
        self.btn_hotspot.setMinimumHeight(32)
        self.btn_hotspot.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.btn_hotspot.setToolTip("在切片上框选按钮区域并添加链接")
        self.btn_hotspot.clicked.connect(self._open_hotspot_editor)
        self.btn_hotspot.setVisible(HOTSPOT_FEATURE_ENABLED)
        _set_test_id(self.btn_hotspot, "hotspotEditorButton")
        self._edit_action_widgets = [self.btn_copy_html, self.btn_adjust_cuts]
        if HOTSPOT_FEATURE_ENABLED:
            self._edit_action_widgets.append(self.btn_hotspot)
        self.step_edit.body.addWidget(self.edit_actions_container)

        # ══ 邮件标题 ════════════════════════
        subject_lbl = QLabel("邮件标题（可选）")
        subject_lbl.setFont(_font("Microsoft YaHei", 11))
        subject_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        self.step_output = WorkflowStep("3  检查并输出")
        root.addWidget(self.step_output)
        self.step_output.body.addWidget(subject_lbl)

        self.input_subject = QLineEdit()
        self.input_subject.setFont(_font("Microsoft YaHei", 12))
        self.input_subject.setPlaceholderText("在此输入邮件标题，留空则使用默认标题")
        self.input_subject.setMinimumHeight(36)
        self.input_subject.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.input_subject.setStyleSheet(_input_style())
        _set_test_id(self.input_subject, "mailSubjectInput")
        self.step_output.body.addWidget(self.input_subject)

        quality_row = QHBoxLayout()
        quality_row.setSpacing(8)
        quality_label = QLabel("发送图片质量：")
        quality_label.setFont(_font("Microsoft YaHei", 10))
        quality_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        self.combo_mail_quality = QComboBox()
        self.combo_mail_quality.addItem("自动（超过 20MB 时询问）", "auto")
        self.combo_mail_quality.addItem("原画质", "original")
        self.combo_mail_quality.addItem(f"压缩至 {COMPRESS_QUALITY}%", "compress")
        self.combo_mail_quality.setMinimumHeight(30)
        self.combo_mail_quality.setStyleSheet(
            f"QComboBox {{ background: {Theme.CARD}; color: {Theme.TEXT_PRIMARY}; "
            f"border: 1px solid {Theme.BORDER}; border-radius: 8px; padding: 3px 10px; }}"
        )
        _set_test_id(self.combo_mail_quality, "mailQualityCombo")
        quality_row.addWidget(quality_label)
        quality_row.addWidget(self.combo_mail_quality, 1)
        self.step_output.body.addLayout(quality_row)

        # ══ 预览区 ═════════════════════════
        self.preview_area = QScrollArea()
        self.preview_area.setWidgetResizable(True)
        self.preview_area.setMinimumHeight(140)
        self.preview_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.preview_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.preview_area.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {Theme.BORDER}; border-radius: 10px; "
            f"background: {Theme.CARD}; }}"
        )
        self.thumb_container = QWidget()
        self.thumb_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.thumb_grid = QGridLayout(self.thumb_container)
        self.thumb_grid.setContentsMargins(8, 8, 8, 8)
        self.thumb_grid.setSpacing(6)
        self.thumb_grid.setSizeConstraint(QGridLayout.SetMinAndMaxSize)
        self.preview_area.setWidget(self.thumb_container)
        self.preview_area.hide()
        self.step_edit.body.addWidget(self.preview_area, stretch=1)

        # ══ 进度条 ═════════════════════════
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ border: none; background: {Theme.BORDER}; border-radius: 9px; "
            f"color: {Theme.TEXT_PRIMARY}; text-align: center; }}"
            f"QProgressBar::chunk {{ background: {Theme.PRIMARY}; border-radius: 9px; }}"
        )
        self.progress_bar.hide()
        self.step_output.body.addWidget(self.progress_bar)

        # ══ 状态 ═══════════════════════════
        self.status_label = QLabel("")
        self.status_label.setFont(_font("Microsoft YaHei", 11))
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(20)
        self.status_label.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
        self.step_output.body.addWidget(self.status_label)

        # ══ 底部按钮区 ═════════════════════
        self.output_actions_container = QWidget()
        self.output_grid = QGridLayout(self.output_actions_container)
        self.output_grid.setSpacing(8)
        self.output_grid.setContentsMargins(0, 4, 0, 0)

        self.btn_send = QPushButton("在 Outlook 中创建邮件")
        self.btn_send.setFont(_font("Microsoft YaHei", 13, QFont.Bold))
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setEnabled(False)
        self.btn_send.setStyleSheet(_btn_primary())
        self.btn_send.setMinimumHeight(42)
        self.btn_send.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_send.setIcon(_icon("mail-white", 18))
        self.btn_send.setIconSize(QSize(18, 18))
        self.btn_send.clicked.connect(self._send_email)
        _set_test_id(self.btn_send, "createOutlookDraftButton")

        self.btn_save = QPushButton("保存切图")
        self.btn_save.setFont(_font("Microsoft YaHei", 12, QFont.Medium))
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setEnabled(False)
        self.btn_save.setStyleSheet(_btn_secondary())
        self.btn_save.setMinimumHeight(42)
        self.btn_save.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_save.setIcon(_icon("arrow-down-to-line", 16))
        self.btn_save.setIconSize(QSize(16, 16))
        self.btn_save.clicked.connect(self._save_slices)
        _set_test_id(self.btn_save, "saveSlicesButton")

        self._output_action_widgets = [self.btn_send, self.btn_save]
        self.step_output.body.addWidget(self.output_actions_container)
        self._apply_responsive_layout(Config.WINDOW_WIDTH)

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
        self._capture_ui_scale_baseline()
        self._apply_ui_scale(self.width(), force=True)

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
        clean = text.strip()
        prefixes = tuple(icons.values())
        while clean.startswith(prefixes):
            for prefix in prefixes:
                if clean.startswith(prefix):
                    clean = clean[len(prefix):].strip()
                    break
        self.status_label.setText(f"{icons.get(level, '')} {clean}".strip())
        self._status_level = level
        self._apply_status_style()

    def _apply_status_style(self):
        colors = {"info": Theme.TEXT_SECONDARY, "success": Theme.SUCCESS,
                  "error": Theme.ERROR, "warning": Theme.WARNING}
        padding = max(1, round(4 * self._ui_scale))
        self.status_label.setStyleSheet(
            f"color: {colors.get(self._status_level, Theme.TEXT_SECONDARY)}; "
            f"background: transparent; padding: {padding}px 0;"
        )

    def _reset_drop_zone(self):
        self.drop_zone.set_compact(False)
        self.drop_zone.title_label.setText("拖拽图片到此处")
        self.drop_zone.icon_label.setPixmap(_icon("upload-cloud", 56).pixmap(56, 56))
        self.drop_zone.tip_label.setText("支持 JPG · PNG · BMP · WebP · GIF · PDF · PPT/PPTX · PSD/PSB，点击上传")

    def _on_width_edited(self):
        """手动输入宽度后校验范围，超限自动修正"""
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
            self.edit_width.setText(str(v))
        except ValueError:
            self.edit_width.setText(str(Config.DEFAULT_WIDTH))

    # ── 快捷键 ──────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        mod = event.modifiers()
        if (mod & Qt.ControlModifier) and event.key() == Qt.Key_O:
            self._select_file()
        elif (mod & Qt.ControlModifier) and event.key() == Qt.Key_V:
            self._paste_image()
        elif (mod & Qt.ControlModifier) and event.key() == Qt.Key_Return:
            if self.btn_send.isEnabled():
                self._create_outlook_mail()
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
        """切换模式时弹预览说明 + 状态反馈。"""
        if bool(state):
            # 导出模式
            self._set_status(
                "导出图片：拖入文件后选择格式和保存路径，只保存到本地",
                "info"
            )
            QMessageBox.information(
                self,
                "导出图片模式",
                "已切换到「导出图片」模式。\n\n"
                "操作流程：\n"
                "1. 拖入图片（支持多张合并）\n"
                "2. 选择输出格式（PNG / JPG）\n"
                "3. 选择保存路径\n\n"
                "导出的图片只保存到本地，不会创建 Outlook 邮件。\n"
                "如需发送邮件，请关闭此开关回到切图模式。"
            )
        else:
            # 切图模式（默认）
            self._set_status(
                "邮件切图模式：拖入后可调整切线、添加链接并创建 Outlook 草稿",
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
                                fmt=er["format"], keep_alpha=er["keep_alpha"],
                                jpg_quality=er["jpg_quality"])
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
                       fmt: str = "png", keep_alpha: bool = True,
                       jpg_quality: int = 85):
        """Start a responsive background export and report progress in the main UI."""
        if self._export_worker is not None and self._export_worker.isRunning():
            QMessageBox.information(self, "正在导出", "当前导出尚未完成，请稍候。")
            return

        if any(Path(path).suffix.lower() in (".pdf", ".ppt", ".pptx", ".psd", ".psb") for path in paths):
            reply = QMessageBox.question(
                self,
                "多页文件确认",
                "检测到可能包含多页的文件，将在后台渲染并合并为一张长图。是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self._set_status("已取消导出", "info")
                return

        if not save_dir:
            save_dir = QFileDialog.getExistingDirectory(
                self, "选择保存目录", self.last_export_dir or ""
            )
            if not save_dir:
                self._set_status("已取消导出", "info")
                return
        if not os.path.isdir(save_dir):
            QMessageBox.critical(self, "导出失败", f"目录不存在：\n{save_dir}")
            self._set_status(f"目录不存在: {save_dir}", "error")
            return

        test_write = os.path.join(save_dir, ".outlook_slicer_write_test")
        try:
            with open(test_write, "w", encoding="utf-8") as handle:
                handle.write("test")
            os.remove(test_write)
        except Exception as exc:
            QMessageBox.critical(
                self, "导出失败", f"目录无写权限：\n{save_dir}\n\n原因：{exc}"
            )
            self._set_status(f"目录无写权限: {save_dir}", "error")
            return

        self.last_export_dir = save_dir
        self._set_status("正在图片导出...", "info")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(5)
        self.progress_bar.show()

        worker = ExportWorker(
            paths=paths,
            save_dir=save_dir,
            fmt=fmt,
            keep_alpha=keep_alpha,
            jpg_quality=jpg_quality,
            renderer=_render_source_to_images,
            parent=self,
        )
        self._export_worker = worker
        worker.progress.connect(self._on_export_progress)
        worker.succeeded.connect(self._on_export_succeeded)
        worker.failed.connect(self._on_export_failed)
        worker.finished.connect(self._on_export_finished)
        worker.start()

    def _on_export_progress(self, value: int, message: str):
        self.progress_bar.setValue(value)
        self._set_status(message, "info")

    def _on_export_succeeded(self, result: dict):
        path = result["path"]
        page_info = f" ({result['page_count']} 页合并)" if result["page_count"] > 1 else ""
        quality_info = (
            f"\nJPG 品质：{result['jpg_quality']}%"
            if result["format"] == "jpg" else ""
        )
        QMessageBox.information(
            self,
            "导出成功",
            f"图片已导出至：\n{path}\n\n"
            f"格式：{result['format'].upper()}{page_info}\n"
            f"大小：{result['size_bytes']:,} 字节{quality_info}\n"
            f"透明底：{'保留' if result['keep_alpha'] else '白底'}",
        )
        self._set_status(f"图片已导出至：{path}", "success")

    def _on_export_failed(self, message: str, details: str):
        QMessageBox.critical(
            self, "导出失败", f"错误：{message}\n\n详细信息：\n{details[:1500]}"
        )
        self._set_status(f"导出失败: {message}", "error")

    def _on_export_finished(self):
        self.progress_bar.hide()
        worker = self._export_worker
        self._export_worker = None
        if worker is not None:
            worker.deleteLater()


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
        self.drop_zone.icon_label.setPixmap(_icon("check", 56).pixmap(56, 56))
        self.drop_zone.tip_label.setText("正在切片处理...")
        self._set_status("正在处理，请稍候...", "info")
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self._start_worker(path)

    def _start_worker(self, path: str):
        self._retire_active_worker()
        self._active_job_id += 1
        job_id = self._active_job_id
        worker = ProcessWorker(path, self._get_width(), smart=self.chk_smart.isChecked())
        self.worker = worker
        worker.progress.connect(lambda value, token=job_id: self._on_worker_progress(token, value))
        worker.finished.connect(
            lambda paths, token=job_id, owner=worker: self._on_processed(paths, token, owner)
        )
        worker.error.connect(
            lambda msg, token=job_id, owner=worker: self._on_error(msg, token, owner)
        )
        worker.finished.connect(lambda _paths, owner=worker: self._release_worker(owner))
        worker.error.connect(lambda _msg, owner=worker: self._release_worker(owner))
        worker.start()

    def _on_worker_progress(self, job_id: int, value: int):
        if job_id == self._active_job_id:
            self.progress_bar.setValue(value)

    def _retire_active_worker(self):
        worker = self.worker
        if worker is None:
            return
        self.worker = None
        worker.requestInterruption()
        if worker.isRunning() and worker not in self._retired_workers:
            self._retired_workers.append(worker)
        elif not worker.isRunning():
            worker.deleteLater()

    def _release_worker(self, worker: ProcessWorker):
        if self.worker is worker:
            self.worker = None
        if worker in self._retired_workers:
            self._retired_workers.remove(worker)
        worker.deleteLater()

    def _on_processed(self, paths: List[str], job_id: Optional[int] = None,
                      worker: Optional[ProcessWorker] = None):
        if job_id is not None and job_id != self._active_job_id:
            cleanup_generated_slices(paths)
            return
        previous_paths = list(self.slice_paths)
        self.slice_paths = paths
        if previous_paths and set(previous_paths) != set(paths):
            cleanup_generated_slices(previous_paths)
        self.drop_zone.set_compact(bool(paths))
        if paths:
            self.drop_zone.title_label.setText("处理完成；可重新拖入文件替换")
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
        if worker is not None and self.worker is worker:
            self.worker = None

    def _on_error(self, msg: str, job_id: Optional[int] = None,
                  worker: Optional[ProcessWorker] = None):
        if job_id is not None and job_id != self._active_job_id:
            return
        self.progress_bar.hide()
        self._set_status(f"❌ 处理失败: {msg}", "error")
        QMessageBox.critical(self, "处理失败", msg)
        if worker is not None and self.worker is worker:
            self.worker = None

    def _show_thumbnails(self, paths: List[str], update_status: bool = True):
        """展示切片缩略图，V4.6.4 加角标 + 双行提示"""
        from PySide6.QtWidgets import QVBoxLayout, QWidget
        scale = self._ui_scale
        px = lambda value: max(1, round(value * scale))
        wrapper_w, wrapper_h = px(128), px(130)
        thumb_w, thumb_h = px(120), px(100)
        available_width = max(1, self.preview_area.viewport().width() - px(20))
        cols = max(1, min(6, available_width // (wrapper_w + px(10))))
        signature = (tuple(paths), wrapper_w, wrapper_h, cols)
        if signature == self._thumbnail_signature and self.thumb_grid.count():
            return

        while self.thumb_grid.count():
            item = self.thumb_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, path in enumerate(paths):
            row, col = divmod(i, cols)
            # 每个缩略图用 QWidget 包裹：上面图，下面文字标识
            wrapper = QWidget()
            wrapper.setFixedSize(wrapper_w, wrapper_h)
            if HOTSPOT_FEATURE_ENABLED:
                wrapper.setCursor(Qt.PointingHandCursor)
                wrapper.setToolTip(
                    f"切片 {i + 1}: {Path(path).name}\n"
                    f"点击可添加/编辑可点击按钮（热区）"
                )
                wrapper.setStyleSheet(
                    "QWidget { background: transparent; }"
                    f"QWidget:hover {{ background: {Theme.DROPZONE_HOVER_BG}; border-radius: {px(8)}px; }}"
                )
            else:
                wrapper.setCursor(Qt.ArrowCursor)
                wrapper.setToolTip(f"切片 {i + 1}: {Path(path).name}")
                wrapper.setStyleSheet("QWidget { background: transparent; }")
            wrapper_layout = QVBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(px(4), px(4), px(4), px(4))
            wrapper_layout.setSpacing(px(2))

            # 图片（V4.8.7: QPixmapCache 避免同一路径多次缩放）
            thumb = QLabel()
            thumb.setFixedSize(thumb_w, thumb_h)
            thumb.setScaledContents(True)
            thumb.setStyleSheet(
                f"background: {Theme.CARD}; border-radius: {px(8)}px; border: 1px solid {Theme.BORDER};"
            )
            from PySide6.QtGui import QPixmapCache
            pix_key = f"thumb_{thumb_w}x{thumb_h}_{path}"
            pix = QPixmapCache.find(pix_key)
            if pix is None or pix.isNull():
                pix = QPixmap(path).scaled(thumb_w, thumb_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                QPixmapCache.insert(pix_key, pix)
            thumb.setPixmap(pix)
            wrapper_layout.addWidget(thumb)

            # 文字标识
            label = QLabel(f"#{i+1}" if not HOTSPOT_FEATURE_ENABLED else f"#{i+1} ✏️ 编辑热区")
            label.setFont(_font(size=9))
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                f"color: {Theme.TEXT_PLACEHOLDER}; background: transparent; padding: {px(2)}px;"
                if not HOTSPOT_FEATURE_ENABLED
                else f"color: {Theme.PRIMARY}; background: transparent; padding: {px(2)}px;"
            )
            wrapper_layout.addWidget(label)

            # 点击缩略图即可为该切片添加/编辑可点击按钮。
            if HOTSPOT_FEATURE_ENABLED:
                wrapper.mousePressEvent = lambda ev, p=path, idx=i: self._on_thumb_clicked(ev, p, idx)
            self.thumb_grid.addWidget(wrapper, row, col)
        self._thumbnail_signature = signature
        self.preview_area.show()
        # V4.6.4：状态条提示缩略图可点
        if update_status and paths and HOTSPOT_FEATURE_ENABLED:
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

    def _validate_hotspots_before_output(self):
        """Validate saved hotspot data immediately before copy or Outlook draft creation."""
        return self.hotspot_map.validate_for_images(self.slice_paths)

    def _copy_html(self):
        """复制 HTML 到剪贴板（同时写入 HTML 和纯文本格式）"""
        if not self.slice_paths:
            return
        # V4.8.7: 记录 materialize 临时文件，复制成功后清理
        temp_files: List[str] = []
        try:
            ok, reason = self._validate_hotspots_before_output()
            if not ok:
                raise ValueError(f"可点击按钮检查失败：{reason}")
            display_w = self._get_width()
            from html_assembler import _materialized_temp_files
            tracked_before = len(_materialized_temp_files)
            raw_slices = self._build_slices_with_hotspots()
            html = generate_plain_html(raw_slices, display_w)
            # 只清理本次 generate_plain_html 新登记的文件。不能 glob 系统临时目录，
            # 否则会误删另一个应用实例仍在使用的 mail_*.png。
            temp_files = list(_materialized_temp_files[tracked_before:])

            clipboard_html = _build_windows_clipboard_html(html)
            if sys.platform == "win32":
                copy_cf_html_to_clipboard(clipboard_html)
            else:
                mime = QMimeData()
                mime.setHtml(html)
                mime.setData("HTML Format", clipboard_html)
                mime.setText(html)
                QGuiApplication.clipboard().setMimeData(mime)
            self._set_status(
                "图片 HTML 已复制；这是手动粘贴兼容方式，链接可靠性低于『创建 Outlook 邮件』",
                "success",
            )
            # V4.8.7: 已复制到剪贴板（base64 内嵌），清理临时文件
            deleted = cleanup_temp_slices(temp_files)
            if deleted:
                self._set_status(f"HTML 已复制（已清理 {deleted} 个临时文件）", "success")
            derived = [
                item.path for item in raw_slices
                if item.path not in set(self.slice_paths)
            ]
            cleanup_generated_slices(derived)
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
            ok, reason = self._validate_hotspots_before_output()
            if not ok:
                raise ValueError(f"可点击按钮检查失败：{reason}")
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
            quality_mode = self.combo_mail_quality.currentData()
            if quality_mode == "compress":
                slices = self._compress_slice_items(slices)
                temp_files.extend(s.path for s in slices)
                compressed_size = estimate_email_size_mb([s.path for s in slices])
                self._set_status(f"已压缩至约 {compressed_size}MB，正在打开邮件...", "success")
            elif quality_mode == "auto" and size_mb > MAX_EMAIL_SIZE_MB:
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
                    temp_files.extend(s.path for s in slices)
                    compressed_size = estimate_email_size_mb([s.path for s in slices])
                    self._set_status(
                        f"已压缩至约 {compressed_size}MB，正在打开邮件...",
                        "success"
                    )

            render_plan = build_render_plan(slices, display_w)
            html_content = assemble_html(slices, display_w, prepared=True)
            subject = self.input_subject.text().strip() or "长图邮件"
            # V4.6.7：传 slices 让 outlook_sender 按 sort_key 排序后取 path
            # image_paths 保留向后兼容
            create_email_with_images(
                html_content, subject=subject, to="",
                slices=slices,
                image_paths=[s.path for s in slices],
                render_plan=render_plan,
            )
            self._set_status("邮件窗口已打开，请检查后发送", "success")
            # V4.8.7: Outlook 已收到 CID 附件，本地临时 PNG 可清理
            deleted = cleanup_temp_slices(temp_files)
            derived = [
                item.path for item in raw_slices
                if item.path not in set(self.slice_paths)
            ]
            cleanup_generated_slices(derived)
            if deleted:
                self._set_status(f"邮件窗口已打开（已清理 {deleted} 个临时文件）", "success")
        except Exception as exc:
            QMessageBox.critical(self, "发送失败", str(exc))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_layout(event.size().width())
        self._apply_ui_scale(event.size().width())
        if self.slice_paths and self.preview_area.isVisible():
            self._show_thumbnails(self.slice_paths, update_status=False)

    def closeEvent(self, event):
        """Cooperatively stop workers; never use QThread.terminate()."""
        workers = [
            worker for worker in [self.worker, self._export_worker, *self._retired_workers]
            if worker is not None
        ]
        for worker in workers:
            worker.requestInterruption()
        still_running = [worker for worker in workers if worker.isRunning() and not worker.wait(5000)]
        if still_running:
            self._set_status("正在安全结束图片处理，请稍后再关闭窗口", "warning")
            event.ignore()
            return
        super().closeEvent(event)

    def _apply_responsive_layout(self, width: int):
        """Reflow edit actions and output buttons without shrinking controls."""
        if not hasattr(self, "edit_actions_grid"):
            return
        edit_columns = 3
        while self.edit_actions_grid.count():
            self.edit_actions_grid.takeAt(0)
        for index, widget in enumerate(self._edit_action_widgets):
            row, column = divmod(index, edit_columns)
            self.edit_actions_grid.addWidget(widget, row, column)
        self.edit_actions_grid.setColumnStretch(edit_columns, 1)

        if not hasattr(self, "output_grid"):
            return
        output_columns = 2
        while self.output_grid.count():
            self.output_grid.takeAt(0)
        for index, widget in enumerate(self._output_action_widgets):
            row, column = divmod(index, output_columns)
            self.output_grid.addWidget(widget, row, column)
        for column in range(output_columns):
            self.output_grid.setColumnStretch(column, 1)

    @staticmethod
    def _scale_stylesheet(style: str, scale: float) -> str:
        def replace(match):
            value = int(match.group(1))
            if value <= 1:
                return f"{value}px"
            return f"{max(1, round(value * scale))}px"

        return re.sub(r"(?<![\w.-])(\d+)px", replace, style)

    def _capture_ui_scale_baseline(self):
        self._scale_widget_baselines = {}
        for widget in self.findChildren(QWidget):
            font = widget.font()
            icon_size = None
            if isinstance(widget, (QPushButton, QCheckBox)):
                icon_size = widget.iconSize()
            self._scale_widget_baselines[widget] = {
                "font_size": font.pointSizeF(),
                "minimum": widget.minimumSize(),
                "maximum": widget.maximumSize(),
                "icon_size": icon_size,
                "style": "" if widget in (self.drop_zone, self.status_label) else widget.styleSheet(),
            }

        self._scale_layout_baselines = {}
        for layout in self.findChildren(QLayout):
            margins = layout.contentsMargins()
            self._scale_layout_baselines[layout] = {
                "margins": (margins.left(), margins.top(), margins.right(), margins.bottom()),
                "spacing": layout.spacing(),
            }
        self._scale_baseline_ready = True

    def _apply_ui_scale(self, width: int, force: bool = False):
        if not self._scale_baseline_ready or self._applying_ui_scale:
            return
        scale = min(1.35, max(0.82, width / Config.WINDOW_WIDTH))
        scale = round(scale * 20) / 20
        if not force and scale == self._ui_scale:
            return

        self._applying_ui_scale = True
        try:
            global _ACTIVE_UI_SCALE
            _ACTIVE_UI_SCALE = scale
            self._ui_scale = scale
            for widget, baseline in self._scale_widget_baselines.items():
                if widget is None:
                    continue
                font_size = baseline["font_size"]
                if font_size > 0:
                    font = widget.font()
                    font.setPointSizeF(max(1.0, font_size * scale))
                    font.setStyleStrategy(
                        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
                    )
                    widget.setFont(font)

                if not isinstance(widget, DropZone):
                    minimum = baseline["minimum"]
                    maximum = baseline["maximum"]
                    widget.setMinimumSize(
                        round(minimum.width() * scale) if minimum.width() > 0 else 0,
                        round(minimum.height() * scale) if minimum.height() > 0 else 0,
                    )
                    widget.setMaximumSize(
                        round(maximum.width() * scale) if maximum.width() < 16777215 else 16777215,
                        round(maximum.height() * scale) if maximum.height() < 16777215 else 16777215,
                    )

                icon_size = baseline["icon_size"]
                if icon_size is not None and icon_size.width() > 0:
                    widget.setIconSize(QSize(
                        max(1, round(icon_size.width() * scale)),
                        max(1, round(icon_size.height() * scale)),
                    ))
                style = baseline["style"]
                if style and "px" in style:
                    widget.setStyleSheet(self._scale_stylesheet(style, scale))

            for layout, baseline in self._scale_layout_baselines.items():
                left, top, right, bottom = baseline["margins"]
                layout.setContentsMargins(
                    round(left * scale), round(top * scale),
                    round(right * scale), round(bottom * scale),
                )
                if baseline["spacing"] >= 0:
                    layout.setSpacing(max(0, round(baseline["spacing"] * scale)))

            self.drop_zone.apply_ui_scale(scale)
            self._apply_status_style()
        finally:
            self._applying_ui_scale = False

    def reset_app(self):
        if self.slice_paths:
            reply = QMessageBox.question(
                self, "确认重置",
                "重置将清除当前所有切片和热区数据，确定继续吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        cleanup_generated_slices(self.slice_paths)
        self.slice_paths = []
        # V4.6.7 修复：重置时同步清空 source_index 映射，避免残留
        self.slice_source_index = {}
        self.file_path = None
        self._active_job_id += 1
        self._retire_active_worker()
        self.hotspot_map.clear()
        self._reset_drop_zone()
        self.input_subject.clear()
        self.edit_width.setText(str(Config.DEFAULT_WIDTH))
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
    _app_icon_path = _resource_file("icon.ico")
    if os.path.exists(_app_icon_path):
        app.setWindowIcon(QIcon(_app_icon_path))
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
