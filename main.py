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
    QLabel, QProgressBar, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent

from image_slicer import detect_and_slice, get_image_info
from pdf_slicer import pdf_to_images
from html_assembler import assemble_html
from outlook_sender import create_email_with_images


class DropArea(QLabel):
    """拖拽区域组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setText("拖拽图片或 PDF 到此处\n或点击选择文件")
        self.setStyleSheet(self._style())
        self.setMinimumSize(400, 300)
        self.file_path: Optional[str] = None

    def _style(self) -> str:
        return """
            QLabel {
                border: 3px dashed #888;
                border-radius: 12px;
                background: #f5f5f5;
                color: #666;
                font-size: 16px;
                padding: 20px;
            }
            QLabel:hover {
                border-color: #0078d4;
                background: #e8f4fc;
            }
        """

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self._style().replace("#f5f5f5", "#e8f4fc"))

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self._style())

    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(self._style())
        urls = event.mimeData().urls()
        if urls:
            self.file_path = urls[0].toLocalFile()
            self.setText(f"已选择: {Path(self.file_path).name}")
            self.parent().parent().on_file_selected(self.file_path)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.file_path: Optional[str] = None
        self.slice_paths: List[str] = []
        self.original_width: int = 0
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Outlook 长图插入工具")
        self.setMinimumSize(600, 500)

        # 中央组件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 标题
        title = QLabel("📎 Outlook 长图无损插入")
        title.setStyleSheet("font-size: 20px; font-weight: bold; padding: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 拖拽区域
        self.drop_area = DropArea()
        layout.addWidget(self.drop_area, stretch=1)

        # 选择文件按钮
        self.btn_select = QPushButton("选择图片/PDF 文件")
        self.btn_select.clicked.connect(self._select_file)
        layout.addWidget(self.btn_select)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # 发送到 Outlook 按钮
        self.btn_send = QPushButton("📤 发送到 Outlook")
        self.btn_send.setEnabled(False)
        self.btn_send.clicked.connect(self._send_to_outlook)
        layout.addWidget(self.btn_send)

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
        self.drop_area.setText(f"已选择: {Path(path).name}")
        self._process_file(path)

    def _process_file(self, path: str):
        """处理文件：切片"""
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # 不确定进度

        try:
            ext = Path(path).suffix.lower()

            if ext == ".pdf":
                # PDF 转图片
                self.progress.setFormat("正在解析 PDF...")
                images = pdf_to_images(path, dpi=150)
                # 保存临时文件
                temp_dir = tempfile.gettempdir()
                self.slice_paths = []
                for i, img in enumerate(images):
                    temp_path = os.path.join(temp_dir, f"pdf_page_{i}.png")
                    img.save(temp_path, "PNG")
                    self.slice_paths.append(temp_path)
                self.original_width = images[0].width if images else 600
            else:
                # 图片切片
                self.progress.setFormat("正在切片...")
                info = get_image_info(path)
                self.original_width = info["width"]
                self.slice_paths = detect_and_slice(path, max_height=1500)

            self.progress.setVisible(False)
            self.btn_send.setEnabled(len(self.slice_paths) > 0)

            QMessageBox.information(
                self, "完成",
                f"处理完成！共 {len(self.slice_paths)} 片\n原始宽度: {self.original_width}px"
            )

        except Exception as e:
            self.progress.setVisible(False)
            QMessageBox.critical(self, "错误", f"处理失败:\n{str(e)}")

    def _send_to_outlook(self):
        """发送到 Outlook"""
        if not self.slice_paths:
            return

        try:
            html = assemble_html(self.slice_paths, self.original_width)
            create_email_with_images(
                html_content=html,
                subject="长图",
                to="",
            )
        except RuntimeError as e:
            QMessageBox.critical(self, "错误", str(e))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"发送失败:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # DPI 适配
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
