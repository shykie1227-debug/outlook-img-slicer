"""
Outlook 长图无损插入工具 - 主程序
PySide6 窗口应用，支持拖拽上传
"""

import os
import sys
import tempfile
from typing import List, Optional
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QProgressBar, QMessageBox, QFileDialog,
    QFrame, QGridLayout, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent, QColor, QPainter, QPen, QBrush

from image_slicer import detect_and_slice, get_image_info
from pdf_slicer import pdf_to_images
from html_assembler import assemble_html
from outlook_sender import create_email_with_images


# ============================================================
# 颜色主题
# ============================================================
class Colors:
    PRIMARY = "#0078D4"       # Microsoft Blue
    PRIMARY_HOVER = "#106EBE"
    PRIMARY_PRESSED = "#005A9E"
    BG_LIGHT = "#F3F6F9"      # 页面背景
    BG_CARD = "#FFFFFF"       # 卡片背景
    BG_DROP = "#F8FAFC"       # 拖拽区背景
    BORDER = "#D0D7DE"        # 边框色
    BORDER_HOVER = "#0078D4"  # hover 边框
    TEXT_PRIMARY = "#24292F"  # 主文字
    TEXT_SECONDARY = "#57606A"  # 次文字
    SUCCESS = "#1B7F37"       # 成功绿
    ERROR = "#CF222E"         # 错误红


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
        self._setup_style()

    def _setup_style(self):
        self.setMinimumHeight(220)
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {Colors.BORDER};
                border-radius: 16px;
                background: {Colors.BG_DROP};
                color: {Colors.TEXT_SECONDARY};
            }}
            QFrame:hover {{
                border-color: {Colors.BORDER_HOVER};
                background: #EBF5FF;
            }}
        "")

    def enterEvent(self, event):
        self._hover = True
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {Colors.BORDER_HOVER};
                border-radius: 16px;
                background: #EBF5FF;
                color: {Colors.TEXT_PRIMARY};
            }}
        """)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._setup_style()
        super().leaveEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(f"""
                QFrame {{
                    border: 2px dashed {Colors.PRIMARY};
                    border-radius: 16px;
                    background: #D4E9FF;
                    color: {Colors.PRIMARY};
                }}
            """)

    def dragLeaveEvent(self, event):
        self._setup_style()

    def dropEvent(self, event: QDropEvent):
        self._setup_style()
        urls = event.mimeData().urls()
        if urls:
            self.file_path = urls[0].toLocalFile()
            self.parent().parent().on_file_selected(self.file_path)


class DropAreaContent(QWidget):
    """拖拽区域内嵌的图标+文字内容"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 30, 20, 30)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignCenter)

        # 图标
        self.icon_label = QLabel("🖼️")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 42px;")

        # 主文字
        self.main_label = QLabel("将图片或 PDF 拖拽到此处")
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 600;
            color: {Colors.TEXT_PRIMARY};
        """)

        # 副文字
        self.sub_label = QLabel("或点击上方按钮选择文件")
        self.sub_label.setAlignment(Qt.AlignCenter)
        self.sub_label.setStyleSheet(f"""
            font-size: 13px;
            color: {Colors.TEXT_SECONDARY};
        """)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.main_label)
        layout.addWidget(self.sub_label)


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
        self.setFixedSize(130, 130)
        self.setStyleSheet(f"""
            QWidget {{
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
            }}
            QWidget:hover {{
                border-color: {Colors.PRIMARY};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 缩略图
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setScaledContents(False)
        pixmap = QPixmap(self.path)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(100, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.img_label.setPixmap(pixmap)
        self.img_label.setStyleSheet("background: transparent;")

        # 文件名
        name = Path(self.path).name
        self.name_label = QLabel(name[:12] + "..." if len(name) > 12 else name)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet(f"""
            font-size: 10px;
            color: {Colors.TEXT_SECONDARY};
        """)

        # 页码
        self.index_label = QLabel(f"#{self.index + 1}")
        self.index_label.setAlignment(Qt.AlignCenter)
        self.index_label.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: {Colors.PRIMARY};
        """)

        layout.addWidget(self.img_label, stretch=1)
        layout.addWidget(self.index_label)
        layout.addWidget(self.name_label)


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.file_path: Optional[str] = None
        self.slice_paths: List[str] = []
        self.original_width: int = 0
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Outlook 长图无损插入工具")
        self.setMinimumSize(700, 580)
        self.resize(720, 620)

        # 整体背景
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {Colors.BG_LIGHT};
            }}
        """)

        # 中央组件
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        # ── 标题栏 ──────────────────────────────────
        title_bar = QWidget()
        title_bar.setStyleSheet(f"""
            background: {Colors.BG_CARD};
            border-radius: 12px;
            border: 1px solid {Colors.BORDER};
        """)
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(20, 14, 20, 14)

        title_icon = QLabel("📎")
        title_icon.setStyleSheet("font-size: 24px;")

        title_text = QLabel("Outlook 长图无损插入")
        title_text.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 700;
            color: {Colors.TEXT_PRIMARY};
        """)

        subtitle_text = QLabel("支持 PNG / JPG / PDF 等格式，自动切片适配页面高度")
        subtitle_text.setStyleSheet(f"""
            font-size: 12px;
            color: {Colors.TEXT_SECONDARY};
        """)

        title_layout.addWidget(title_icon)
        title_layout.addSpacing(10)
        title_layout.addWidget(title_text)
        title_layout.addStretch()
        title_layout.addWidget(subtitle_text)

        outer.addWidget(title_bar)

        # ── 拖拽区域 ──────────────────────────────────
        drop_container = QWidget()
        drop_container.setStyleSheet(f"""
            background: {Colors.BG_CARD};
            border-radius: 14px;
            border: 1px solid {Colors.BORDER};
        """)
        drop_layout = QVBoxLayout(drop_container)
        drop_layout.setContentsMargins(0, 0, 0, 0)

        self.drop_area = DropArea()
        self.drop_content = DropAreaContent()
        # 用栈式布局让内容覆盖整个 drop area
        drop_inner = QVBoxLayout(self.drop_area)
        drop_inner.setContentsMargins(0, 0, 0, 0)
        drop_inner.addWidget(self.drop_content, alignment=Qt.AlignCenter)

        # 选择文件按钮（放在拖拽区下方）
        self.btn_select = QPushButton("📂 选择图片 / PDF 文件")
        self.btn_select.setCursor(Qt.PointingHandCursor)
        self.btn_select.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.PRIMARY};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {Colors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background: {Colors.PRIMARY_PRESSED};
            }}
        """)
        self.btn_select.clicked.connect(self._select_file)

        drop_layout.addWidget(self.drop_area, stretch=1)
        drop_layout.addSpacing(8)
        drop_layout.addWidget(self.btn_select, alignment=Qt.AlignCenter)
        drop_layout.addSpacing(10)

        outer.addWidget(drop_container, stretch=1)

        # ── 缩略图预览区 ──────────────────────────────────
        self.thumbnail_area = QScrollArea()
        self.thumbnail_area.setVisible(False)
        self.thumbnail_area.setStyleSheet(f"""
            QScrollArea {{
                background: {Colors.BG_CARD};
                border-radius: 12px;
                border: 1px solid {Colors.BORDER};
            }}
        """)
        self.thumbnail_area.setWidgetResizable(True)
        self.thumbnail_area.setFixedHeight(150)

        thumb_container = QWidget()
        self.thumb_layout = QGridLayout(thumb_container)
        self.thumb_layout.setSpacing(8)
        self.thumbnail_area.setWidget(thumb_container)

        outer.addWidget(self.thumbnail_area)

        # ── 进度条 ──────────────────────────────────
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background: {Colors.BG_CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
                text-align: center;
                height: 28px;
                font-size: 13px;
                font-weight: 600;
                color: {Colors.PRIMARY};
            }}
            QProgressBar::chunk {{
                background: {Colors.PRIMARY};
                border-radius: 7px;
            }}
        """)
        outer.addWidget(self.progress)

        # ── 状态标签 ──────────────────────────────────
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"""
            font-size: 13px;
            color: {Colors.TEXT_SECONDARY};
            padding: 2px;
        """)
        outer.addWidget(self.status_label)

        # ── 发送到 Outlook 按钮 ──────────────────────────────────
        self.btn_send = QPushButton("📤 发送到 Outlook")
        self.btn_send.setEnabled(False)
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.PRIMARY};
                color: white;
                border: none;
                border-radius: 10px;
                padding: 14px 32px;
                font-size: 16px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {Colors.PRIMARY_HOVER};
            }}
            QPushButton:pressed {{
                background: {Colors.PRIMARY_PRESSED};
            }}
            QPushButton:disabled {{
                background: #BDC3C7;
            }}
        """)
        self.btn_send.setMinimumHeight(52)
        outer.addWidget(self.btn_send)

        self.btn_send.clicked.connect(self._send_to_outlook)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片或 PDF",
            "",
            "图片 (*.png *.jpg *.jpeg *.bmp *.webp *.gif);;PDF (*.pdf)"
        )
        if path:
            self.on_file_selected(path)

    def on_file_selected(self, path: str):
        """文件选择后的处理"""
        self.file_path = path
        filename = Path(path).name

        # 更新拖拽区显示
        self.drop_area.setStyleSheet(f"""
            QFrame {{
                border: 2px dashed {Colors.SUCCESS};
                border-radius: 16px;
                background: #F0FFF4;
                color: {Colors.SUCCESS};
            }}
        """)
        self.drop_content.icon_label.setText("✅")
        self.drop_content.main_label.setText(f"已选择: {filename}")
        self.drop_content.sub_label.setText("点击上方按钮重新选择")

        self._process_file(path)

    def _update_thumbnails(self):
        """更新缩略图预览"""
        # 清除旧卡片
        while self.thumb_layout.count():
            child = self.thumb_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not self.slice_paths:
            self.thumbnail_area.setVisible(False)
            return

        self.thumbnail_area.setVisible(True)
        cols = 5
        for i, path in enumerate(self.slice_paths):
            row = i // cols
            col = i % cols
            card = ThumbnailCard(i, path)
            self.thumb_layout.addWidget(card, row, col)

        # 确保容器有足够高度
        rows = (len(self.slice_paths) + cols - 1) // cols
        self.thumbnail_area.widget().setMinimumHeight(rows * 140)

    def _process_file(self, path: str):
        """处理文件：切片"""
        self.progress.setVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(10)
        self.progress.setFormat("正在解析文件...")

        try:
            ext = Path(path).suffix.lower()
            self.progress.setValue(30)

            if ext == ".pdf":
                self.progress.setFormat("正在转换 PDF...")
                images = pdf_to_images(path, dpi=150)
                temp_dir = tempfile.gettempdir()
                self.slice_paths = []
                for i, img in enumerate(images):
                    temp_path = os.path.join(temp_dir, f"pdf_page_{i}.png")
                    img.save(temp_path, "PNG")
                    self.slice_paths.append(temp_path)
                self.original_width = images[0].width if images else 600
            else:
                self.progress.setValue(50)
                self.progress.setFormat("正在切片...")
                info = get_image_info(path)
                self.original_width = info["width"]
                self.slice_paths = detect_and_slice(path, max_height=1500)

            self.progress.setValue(90)

            # 更新缩略图
            self._update_thumbnails()

            self.progress.setValue(100)
            self.progress.setFormat(f"完成！共 {len(self.slice_paths)} 片")

            self.status_label.setText(
                f"✅ 处理完成 · 原始宽度 {self.original_width}px · 共 {len(self.slice_paths)} 片"
            )
            self.status_label.setStyleSheet(f"""
                font-size: 13px;
                color: {Colors.SUCCESS};
                font-weight: 600;
                padding: 4px;
            """)

            self.btn_send.setEnabled(len(self.slice_paths) > 0)

        except Exception as e:
            self.progress.setVisible(False)
            self.status_label.setText("")
            QMessageBox.critical(
                self, "❌ 处理失败",
                f"处理文件时出错:\n{str(e)}"
            )

    def _send_to_outlook(self):
        """发送到 Outlook"""
        if not self.slice_paths:
            return

        self.btn_send.setEnabled(False)
        self.status_label.setText("正在启动 Outlook...")

        try:
            html = assemble_html(self.slice_paths, self.original_width)
            create_email_with_images(
                html_content=html,
                subject="长图",
                to="",
            )
            self.status_label.setText("✅ 邮件已创建，请在 Outlook 中发送")
            self.status_label.setStyleSheet(f"""
                font-size: 14px;
                color: {Colors.SUCCESS};
                font-weight: 600;
                padding: 6px;
            """)
            self.btn_send.setEnabled(True)

        except RuntimeError as e:
            QMessageBox.critical(self, "❌ 错误", str(e))
            self.btn_send.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "❌ 发送失败", f"发送失败:\n{str(e)}")
            self.btn_send.setEnabled(True)


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # DPI 适配
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())