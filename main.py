"""
Outlook 长图无损插入工具 - 主程序
PySide6 窗口应用，支持拖拽上传
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
    QFrame, QGridLayout, QScrollArea, QSizePolicy,
    QLineEdit, QSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QImageReader

from image_slicer import detect_and_slice, get_image_info
from pdf_slicer import pdf_to_images
from html_assembler import assemble_html
from outlook_sender import create_email_with_images


# ============================================================
# 颜色主题
# ============================================================
C = type("C", (), {
    "PRIMARY": "#0078D4",
    "PRIMARY_HOVER": "#106EBE",
    "PRIMARY_PRESSED": "#005A9E",
    "BG_LIGHT": "#F3F6F9",
    "BG_CARD": "#FFFFFF",
    "BG_DROP": "#F8FAFC",
    "BORDER": "#D0D7DE",
    "BORDER_HOVER": "#0078D4",
    "TEXT_PRIMARY": "#24292F",
    "TEXT_SECONDARY": "#57606A",
    "SUCCESS": "#1B7F37",
    "ERROR": "#CF222E",
})()


def css(primary=C.PRIMARY, bg_light=C.BG_LIGHT, border=C.BORDER,
        border_hover=C.BORDER_HOVER, text_primary=C.TEXT_PRIMARY,
        text_secondary=C.TEXT_SECONDARY, bg_card=C.BG_CARD,
        success=C.SUCCESS, error=C.ERROR, bg_drop=C.BG_DROP,
        primary_hover=C.PRIMARY_HOVER, primary_pressed=C.PRIMARY_PRESSED):
    """生成 CSS 字符串，避免 f-string 嵌套大括号问题"""
    return {
        "primary": primary, "bg_light": bg_light, "border": border,
        "border_hover": border_hover, "text_primary": text_primary,
        "text_secondary": text_secondary, "bg_card": bg_card,
        "success": success, "error": error, "bg_drop": bg_drop,
        "primary_hover": primary_hover, "primary_pressed": primary_pressed,
    }


# ============================================================
# 拖拽区域组件
# ============================================================
class DropArea(QFrame):
    """拖拽区域组件 - 现代化虚线边框样式"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._hover = False
        self.file_path: Optional[str] = None
        self._setup_ui()
        self._setup_style()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 40, 20, 40)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel("🖼️")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 42px; font-family: Segoe UI Emoji;")

        self.main_label = QLabel("将图片或 PDF 拖拽到此处")
        self.main_label.setAlignment(Qt.AlignCenter)
        s = "font-size: 16px; font-weight: 600; color: " + C.TEXT_PRIMARY + ";"
        self.main_label.setStyleSheet(s)

        self.sub_label = QLabel("或点击上方按钮选择文件")
        self.sub_label.setAlignment(Qt.AlignCenter)
        s2 = "font-size: 13px; color: " + C.TEXT_SECONDARY + ";"
        self.sub_label.setStyleSheet(s2)

        self.hint_label = QLabel("支持 JPG, PNG, BMP, WebP, GIF, PDF")
        self.hint_label.setAlignment(Qt.AlignCenter)
        s3 = "font-size: 11px; color: " + C.TEXT_SECONDARY + ";"
        self.hint_label.setStyleSheet(s3)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.main_label)
        layout.addWidget(self.sub_label)
        layout.addWidget(self.hint_label)

    def _setup_style(self):
        s = (
            "QFrame {"
            "border: 2px dashed " + C.BORDER + ";"
            "border-radius: 16px;"
            "background: " + C.BG_DROP + ";"
            "}"
        )
        self.setStyleSheet(s)

    def enterEvent(self, event):
        self._hover = True
        s = (
            "QFrame {"
            "border: 2px dashed " + C.BORDER_HOVER + ";"
            "border-radius: 16px;"
            "background: #EBF5FF;"
            "}"
        )
        self.setStyleSheet(s)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._setup_style()
        super().leaveEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            s = (
                "QFrame {"
                "border: 2px dashed " + C.PRIMARY + ";"
                "border-radius: 16px;"
                "background: #D4E9FF;"
                "}"
            )
            self.setStyleSheet(s)
            self.icon_label.setText("📥")
            self.main_label.setText("松开即可添加")
            s2 = "font-size: 16px; font-weight: 600; color: " + C.PRIMARY + ";"
            self.main_label.setStyleSheet(s2)

    def dragLeaveEvent(self, event):
        self._setup_style()
        self.icon_label.setText("🖼️")
        self.main_label.setText("将图片或 PDF 拖拽到此处")
        s = "font-size: 16px; font-weight: 600; color: " + C.TEXT_PRIMARY + ";"
        self.main_label.setStyleSheet(s)

    def dropEvent(self, event: QDropEvent):
        self._setup_style()
        urls = event.mimeData().urls()
        if urls:
            self.file_path = urls[0].toLocalFile()
            self.parent().parent().on_file_selected(self.file_path)


# ============================================================
# 缩略图卡片
# ============================================================
class ThumbnailCard(QWidget):
    """单个切片缩略图卡片"""
    def __init__(self, index: int, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        self.index = index
        self._build_ui()

    def _build_ui(self):
        self.setFixedSize(130, 145)
        s = (
            "QWidget {"
            "background: " + C.BG_CARD + ";"
            "border: 1px solid " + C.BORDER + ";"
            "border-radius: 10px;"
            "}"
        )
        self.setStyleSheet(s)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 图片
        self.img_label = QLabel()
        self.img_label.setFixedSize(118, 100)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("background: transparent; border: none;")
        pixmap = QPixmap(self.path)
        if pixmap.width() > 118 or pixmap.height() > 100:
            pixmap = pixmap.scaled(118, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.img_label.setPixmap(pixmap)

        # 页码
        self.index_label = QLabel("#" + str(self.index + 1))
        self.index_label.setAlignment(Qt.AlignCenter)
        s2 = "font-size: 11px; color: " + C.TEXT_SECONDARY + ";"
        self.index_label.setStyleSheet(s2)

        layout.addWidget(self.img_label)
        layout.addWidget(self.index_label)


# ============================================================
# 后台处理线程
# ============================================================
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
            self.progress.emit(10)
            if ext == ".pdf":
                images = pdf_to_images(self.file_path)
                self.progress.emit(30)
                slice_paths = []
                temp_dir = tempfile.gettempdir()
                for i, img in enumerate(images):
                    path = os.path.join(temp_dir, f"pdf_page_{i}.png")
                    img.save(path)
                    slice_paths.append(path)
                self.progress.emit(60)
            else:
                slice_paths = detect_and_slice(self.file_path)
                self.progress.emit(60)
            self.progress.emit(100)
            self.finished.emit(slice_paths)
        except Exception as e:
            self.error.emit(str(e))


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.slice_paths: List[str] = []
        self.file_path: Optional[str] = None
        self.worker: Optional[ProcessWorker] = None
        self._setup_ui()
        self._setup_style()

    def _setup_ui(self):
        self.setWindowTitle("Outlook 长图插入工具")
        self.setFixedSize(720, 640)

        # 标题栏
        title_bar = QWidget()
        title_bar.setFixedHeight(70)
        title_bar.setStyleSheet("background: " + C.PRIMARY + ";")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(20, 0, 20, 0)
        title_icon = QLabel("📧")
        title_icon.setStyleSheet("font-size: 28px; font-family: Segoe UI Emoji;")
        title_text = QLabel("Outlook 长图插入工具")
        title_text.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: white; font-family: Microsoft YaHei, sans-serif;")
        subtitle_text = QLabel("Outlook 邮件长图无损插入 · 自动切片 · 绿色免安装")
        subtitle_text.setStyleSheet(
            "font-size: 12px; color: rgba(255,255,255,0.8); font-family: Microsoft YaHei, sans-serif;")
        title_right = QVBoxLayout()
        title_right.setSpacing(2)
        title_right.addWidget(title_text)
        title_right.addWidget(subtitle_text)
        title_layout.addWidget(title_icon)
        title_layout.addLayout(title_right)
        title_layout.addStretch()

        # 主内容区
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)

        # 标题栏
        main_layout.addWidget(title_bar, alignment=Qt.AlignTop)

        # 拖拽区
        self.drop_area = DropArea()
        main_layout.addWidget(self.drop_area)

        # 操作区
        op_widget = QWidget()
        op_layout = QVBoxLayout(op_widget)
        op_layout.setSpacing(10)

        # 第一行：选择文件 + 宽度调整
        row1 = QWidget()
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_select = QPushButton("📁 选择文件")
        self.btn_select.setFixedHeight(38)
        self.btn_select.clicked.connect(self._select_file)
        s = (
            "QPushButton {"
            "background: " + C.BG_CARD + ";"
            "border: 1px solid " + C.BORDER + ";"
            "border-radius: 8px;"
            "padding: 0 16px;"
            "font-size: 14px;"
            "color: " + C.TEXT_PRIMARY + ";"
            "}"
            "QPushButton:hover {"
            "border-color: " + C.PRIMARY + ";"
            "color: " + C.PRIMARY + ";"
            "}"
        )
        self.btn_select.setStyleSheet(s)

        self.btn_remove = QPushButton("🗑️ 移除")
        self.btn_remove.setFixedHeight(38)
        self.btn_remove.setFixedWidth(100)
        self.btn_remove.clicked.connect(self._remove_file)
        self.btn_remove.setEnabled(False)
        s2 = (
            "QPushButton {"
            "background: " + C.BG_CARD + ";"
            "border: 1px solid " + C.BORDER + ";"
            "border-radius: 8px;"
            "padding: 0 12px;"
            "font-size: 14px;"
            "color: " + C.TEXT_SECONDARY + ";"
            "}"
            "QPushButton:hover {"
            "border-color: " + C.ERROR + ";"
            "color: " + C.ERROR + ";"
            "}"
        )
        self.btn_remove.setStyleSheet(s2)

        row1_layout.addWidget(self.btn_select)
        row1_layout.addWidget(self.btn_remove)
        row1_layout.addStretch()

        # 第二行：宽度调整 + 邮件标题
        row2 = QWidget()
        row2_layout = QHBoxLayout(row2)
        row2_layout.setSpacing(12)

        width_label = QLabel("图片宽度:")
        width_label.setStyleSheet(
            "font-size: 14px; color: " + C.TEXT_SECONDARY + ";")
        self.width_spin = QSpinBox()
        self.width_spin.setRange(300, 2000)
        self.width_spin.setValue(1000)
        self.width_spin.setSuffix(" px")
        self.width_spin.setFixedWidth(120)
        s3 = (
            "QSpinBox {"
            "border: 1px solid " + C.BORDER + ";"
            "border-radius: 6px;"
            "padding: 4px 8px;"
            "font-size: 14px;"
            "}"
        )
        self.width_spin.setStyleSheet(s3)

        subject_label = QLabel("邮件标题:")
        subject_label.setStyleSheet(
            "font-size: 14px; color: " + C.TEXT_SECONDARY + ";")
        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("请输入邮件标题（可选）")
        self.subject_input.setFixedHeight(36)
        s4 = (
            "QLineEdit {"
            "border: 1px solid " + C.BORDER + ";"
            "border-radius: 6px;"
            "padding: 4px 12px;"
            "font-size: 14px;"
            "}"
            "QLineEdit:focus {"
            "border-color: " + C.PRIMARY + ";"
            "}"
        )
        self.subject_input.setStyleSheet(s4)

        row2_layout.addWidget(width_label)
        row2_layout.addWidget(self.width_spin)
        row2_layout.addSpacing(16)
        row2_layout.addWidget(subject_label)
        row2_layout.addWidget(self.subject_input, stretch=1)

        op_layout.addWidget(row1)
        op_layout.addWidget(row2)
        main_layout.addWidget(op_widget)

        # 缩略图区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(180)
        s5 = "QScrollArea { border: none; background: transparent; }"
        scroll.setStyleSheet(s5)

        self.thumbnail_container = QWidget()
        self.thumbnail_grid = QGridLayout(self.thumbnail_container)
        self.thumbnail_grid.setSpacing(8)
        self.thumbnail_area = ThumbnailArea()
        self.thumbnail_area.setWidget(self.thumbnail_container)
        self.thumbnail_area.setWidgetResizable(True)
        s6 = (
            "QScrollArea { border: 1px solid " + C.BORDER + ";"
            "border-radius: 10px;"
            "background: " + C.BG_CARD + ";"
            "}"
        )
        self.thumbnail_area.setStyleSheet(s6)
        self.thumbnail_area.hide()
        main_layout.addWidget(self.thumbnail_area)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        s7 = (
            "QProgressBar {"
            "border: none;"
            "border-radius: 3px;"
            "background: " + C.BORDER + ";"
            "}"
            "QProgressBar::chunk {"
            "background: " + C.PRIMARY + ";"
            "border-radius: 3px;"
            "}"
        )
        self.progress.setStyleSheet(s7)
        self.progress.hide()
        main_layout.addWidget(self.progress)

        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedHeight(24)
        main_layout.addWidget(self.status_label)

        # 发送按钮
        self.btn_send = QPushButton("📨 发送到 Outlook")
        self.btn_send.setFixedHeight(52)
        self.btn_send.setEnabled(False)
        self.btn_send.clicked.connect(self._send_email)
        s8 = (
            "QPushButton {"
            "background: " + C.PRIMARY + ";"
            "color: white;"
            "border: none;"
            "border-radius: 10px;"
            "font-size: 16px;"
            "font-weight: bold;"
            "}"
            "QPushButton:hover {"
            "background: " + C.PRIMARY_HOVER + ";"
            "}"
            "QPushButton:pressed {"
            "background: " + C.PRIMARY_PRESSED + ";"
            "}"
            "QPushButton:disabled {"
            "background: " + C.BORDER + ";"
            "color: " + C.TEXT_SECONDARY + ";"
            "}"
        )
        self.btn_send.setStyleSheet(s8)
        main_layout.addWidget(self.btn_send)

    def _setup_style(self):
        s = "background: " + C.BG_LIGHT + ";"
        self.setStyleSheet(s)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片或 PDF",
            "", "图片 (*.jpg *.jpeg *.png *.bmp *.webp *.gif);;PDF (*.pdf)"
        )
        if path:
            self.on_file_selected(path)

    def _remove_file(self):
        self.slice_paths = []
        self.file_path = None
        self.thumbnail_area.hide()
        self.btn_send.setEnabled(False)
        self.btn_remove.setEnabled(False)
        self.status_label.setText("")
        self.drop_area._setup_style()
        self.drop_area.icon_label.setText("🖼️")
        self.drop_area.main_label.setText("将图片或 PDF 拖拽到此处")
        s = "font-size: 16px; font-weight: 600; color: " + C.TEXT_PRIMARY + ";"
        self.drop_area.main_label.setStyleSheet(s)

    def on_file_selected(self, path: str):
        self.file_path = path
        self.slice_paths = []
        self.drop_area._setup_style()
        self.drop_area.icon_label.setText("✅")
        self.drop_area.main_label.setText(Path(path).name)
        s = "font-size: 14px; font-weight: 600; color: " + C.SUCCESS + ";"
        self.drop_area.main_label.setStyleSheet(s)
        self.btn_remove.setEnabled(True)
        self.status_label.setText("正在处理...")
        s2 = "color: " + C.TEXT_SECONDARY + "; font-size: 13px;"
        self.status_label.setStyleSheet(s2)
        self.progress.show()
        self.progress.setValue(0)

        self.worker = ProcessWorker(path, self.width_spin.value())
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_processed)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, val: int):
        self.progress.setValue(val)

    def _on_processed(self, paths: List[str]):
        self.slice_paths = paths
        self.progress.setValue(100)
        self.progress.hide()
        self._show_thumbnails(paths)
        self.btn_send.setEnabled(True)
        self.status_label.setText(
            f"✅ 已处理 {len(paths)} 张切片，可发送到 Outlook")
        s = "color: " + C.SUCCESS + "; font-size: 13px;"
        self.status_label.setStyleSheet(s)

    def _on_error(self, msg: str):
        self.progress.hide()
        self.status_label.setText("❌ 处理失败: " + msg)
        s = "color: " + C.ERROR + "; font-size: 13px;"
        self.status_label.setStyleSheet(s)

    def _show_thumbnails(self, paths: List[str]):
        # 清空旧缩略图
        while self.thumbnail_grid.count():
            item = self.thumbnail_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 5
        for i, path in enumerate(paths):
            row = i // cols
            col = i % cols
            card = ThumbnailCard(i, path)
            self.thumbnail_grid.addWidget(card, row, col)

        self.thumbnail_area.show()

    def _send_email(self):
        if not self.slice_paths:
            return
        subject = self.subject_input.text().strip() or "长图邮件"
        width = self.width_spin.value()
        try:
            html = assemble_html(self.slice_paths, width)
            create_email_with_images(html, subject, "", None)
            self.status_label.setText("✅ 邮件已创建，请在 Outlook 中编辑并发送")
            s = "color: " + C.SUCCESS + "; font-size: 13px;"
            self.status_label.setStyleSheet(s)
        except Exception as e:
            QMessageBox.critical(self, "发送失败", str(e))


class ThumbnailArea(QScrollArea):
    """缩略图滚动区域"""
    pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
