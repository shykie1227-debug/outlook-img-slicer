"""
图片导出格式选择弹窗（V4.6.3 新增）

用户选「图片导出」模式后弹出此窗：
  1. 选择输出格式：JPG / PNG
  2. 选择是否保留透明底（仅 PNG 支持，JPG 强制白底）
  3. 选择保存路径

UI 示意：
  ┌──────────────────────────────────────┐
  │ 🖼️ 图片导出 — 选择格式                 │
  │                                      │
  │ 已拖入 3 个文件（共 5.2MB）           │
  │                                      │
  │ 输出格式:                             │
  │   (●) 🖼️ PNG（推荐 — 无损，支持透明）  │
  │   ( ) 📷 JPG（更小体积，白底）         │
  │                                      │
  │   [✓] 保留透明底（仅 PNG 有效）       │
  │   ⚠️ 源图若无透明则此选项无效果       │
  │                                      │
  │ 保存路径:                             │
  │   [_________________________] [浏览]  │
  │                                      │
  │            [确定]  [取消]             │
  └──────────────────────────────────────┘
"""
from typing import List, Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QRadioButton,
    QButtonGroup, QLineEdit, QFileDialog, QGroupBox, QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

import os


# ── 格式常量 ───────────────────────────────────────
FMT_PNG = "png"  # 无损，支持透明
FMT_JPG = "jpg"  # 有损，白底


class ExportFormatDialog(QDialog):
    """
    图片导出格式选择弹窗。
    Returns: (format, keep_alpha, save_dir) via .get_result()
    """

    def __init__(self, file_paths: List[str], parent=None, initial_save_dir: Optional[str] = None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.format: str = FMT_PNG  # 默认 PNG
        self.keep_alpha: bool = True  # 默认保留透明
        self.save_dir: Optional[str] = initial_save_dir if initial_save_dir else None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("图片导出 - 选择格式")
        self.setMinimumSize(520, 380)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        # ── 1. 文件信息 ──
        file_info = self._summarize_files()
        info_lbl = QLabel(file_info)
        info_lbl.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        info_lbl.setStyleSheet(
            "color: #0078D4; background: #EFF6FF; padding: 10px 12px; "
            "border-radius: 6px; border: 1px solid #BFDBFE;"
        )
        info_lbl.setWordWrap(True)
        root.addWidget(info_lbl)

        # ── 2. 输出格式选择 ──
        fmt_group = QGroupBox("输出格式")
        fmt_group.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        fmt_layout = QVBoxLayout(fmt_group)
        fmt_layout.setSpacing(6)

        self.radio_png = QRadioButton("🖼️  PNG（推荐 — 无损，支持透明底）")
        self.radio_png.setFont(QFont("Microsoft YaHei", 11))
        self.radio_png.setChecked(True)
        self.radio_png.setToolTip("PNG 格式无损，支持透明背景，文件较大")
        self.radio_png.toggled.connect(self._on_format_changed)

        self.radio_jpg = QRadioButton("📷  JPG（更小体积，强制白底）")
        self.radio_jpg.setFont(QFont("Microsoft YaHei", 11))
        self.radio_jpg.setToolTip("JPG 格式有损压缩，文件小，但不支持透明底（强制白色背景）")
        self.radio_jpg.toggled.connect(self._on_format_changed)

        fmt_layout.addWidget(self.radio_png)
        fmt_layout.addWidget(self.radio_jpg)
        root.addWidget(fmt_group)

        # ── 3. 透明底选项（仅 PNG 有效） ──
        alpha_group = QGroupBox("背景选项")
        alpha_group.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        alpha_layout = QVBoxLayout(alpha_group)
        alpha_layout.setSpacing(4)

        self.chk_alpha = QCheckBox("✓ 保留透明底（仅 PNG 格式有效）")
        self.chk_alpha.setFont(QFont("Microsoft YaHei", 10))
        self.chk_alpha.setChecked(True)
        self.chk_alpha.setToolTip(
            "勾选：源图透明区域在导出后仍然透明（仅 PNG）\n"
            "不勾选：透明区域填充为白色（适合邮件等场景）"
        )

        self.alpha_hint = QLabel("💡 当前 PNG 格式，可选透明底")
        self.alpha_hint.setFont(QFont("Microsoft YaHei", 9))
        self.alpha_hint.setStyleSheet("color: #6B7280; background: transparent;")

        alpha_layout.addWidget(self.chk_alpha)
        alpha_layout.addWidget(self.alpha_hint)
        root.addWidget(alpha_group)

        # ── 4. 保存路径 ──
        save_group = QGroupBox("保存路径（必填）")
        save_group.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        save_layout = QHBoxLayout(save_group)

        self.input_save = QLineEdit()
        self.input_save.setPlaceholderText("例如 D:\\我的图片\\outlook-export")
        self.input_save.setFont(QFont("Microsoft YaHei", 10))
        if self.save_dir:
            self.input_save.setText(self.save_dir)
        save_layout.addWidget(self.input_save, 1)

        btn_browse = QPushButton("浏览…")
        btn_browse.setFont(QFont("Microsoft YaHei", 10))
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.clicked.connect(self._browse_save_dir)
        save_layout.addWidget(btn_browse)

        root.addWidget(save_group)

        # ── 5. 按钮 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.setFont(QFont("Microsoft YaHei", 11))
        btn_cancel.setFixedSize(90, 34)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_ok = QPushButton("导出")
        btn_ok.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        btn_ok.setFixedSize(90, 34)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setStyleSheet(
            "QPushButton { background: #0078D4; color: white; border: none; border-radius: 6px; }"
            "QPushButton:hover { background: #2563EB; }"
        )
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_accept)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    def _summarize_files(self) -> str:
        n = len(self.file_paths)
        try:
            total_size = sum(os.path.getsize(p) for p in self.file_paths)
            if total_size < 1024 * 1024:
                size_str = f"{total_size / 1024:.1f}KB"
            else:
                size_str = f"{total_size / 1024 / 1024:.1f}MB"
        except Exception:
            size_str = "未知"
        if n == 1:
            return f"📄 已拖入文件：{Path(self.file_paths[0]).name}（{size_str}）"
        return f"📦 已拖入 {n} 个文件（共 {size_str}）"

    def _on_format_changed(self):
        """格式切换：JPG 强制白底，PNG 可选透明底"""
        if self.radio_jpg.isChecked():
            self.chk_alpha.setEnabled(False)
            self.chk_alpha.setChecked(False)
            self.alpha_hint.setText("⚠️ JPG 格式强制白底，透明底选项已禁用")
            self.alpha_hint.setStyleSheet("color: #DC2626; background: transparent;")
        else:
            self.chk_alpha.setEnabled(True)
            self.alpha_hint.setText("💡 当前 PNG 格式，可选透明底")
            self.alpha_hint.setStyleSheet("color: #6B7280; background: transparent;")

    def _browse_save_dir(self):
        current = self.input_save.text().strip()
        start_dir = current if current and os.path.isdir(current) else os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(self, "选择保存目录", start_dir)
        if chosen:
            self.input_save.setText(chosen)

    def _on_accept(self):
        # 1. 格式
        self.format = FMT_PNG if self.radio_png.isChecked() else FMT_JPG

        # 2. 透明底（仅 PNG 有效）
        self.keep_alpha = self.chk_alpha.isChecked() and self.format == FMT_PNG

        # 3. 保存路径
        save_path = self.input_save.text().strip()
        if not save_path:
            QMessageBox.warning(self, "请选择保存路径", "图片导出需要指定保存目录。")
            return
        if not os.path.isdir(save_path):
            reply = QMessageBox.question(
                self, "目录不存在",
                f"目录不存在：\n{save_path}\n\n是否创建该目录？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                try:
                    os.makedirs(save_path, exist_ok=True)
                except Exception as e:
                    QMessageBox.critical(self, "创建失败", f"无法创建目录：\n{e}")
                    return
            else:
                return
        self.save_dir = save_path

        self.accept()

    def get_result(self) -> dict:
        return {
            "format": self.format,
            "keep_alpha": self.keep_alpha,
            "save_dir": self.save_dir,
            "file_paths": self.file_paths,
        }
