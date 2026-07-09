r"""
图片导出格式选择弹窗

用户选「图片导出」模式后弹出此窗：
  1. 选择输出格式：JPG / PNG
  2. 选择是否保留透明底（仅 PNG 支持，JPG 强制白底）
  3. JPG 压缩质量滑块（仅 JPG 有效）
  4. 选择保存路径

UI 示意：
  ┌──────────────────────────────────────────┐
  │  已拖入 3 个文件（共 5.2MB）                │
  │                                          │
  │  输出格式                                 │
  │  ┌────────────────────────────────────┐  │
  │  │ (●) PNG（无损，支持透明底）        │  │
  │  │ ( ) JPG（更小体积，强制白底）      │  │
  │  └────────────────────────────────────┘  │
  │                                          │
  │  背景选项                                 │
  │  ┌────────────────────────────────────┐  │
  │  │ [✓] 保留透明底（仅 PNG 有效）      │  │
  │  │ 当前 PNG 格式，可选透明底           │  │
  │  └────────────────────────────────────┘  │
  │                                          │
  │  JPG 品质（仅 JPG 有效）                   │
  │  ┌────────────────────────────────────┐  │
  │  │  ════════════●════════  85%         │  │
  │  │  品质越高文件越大，推荐 75-85%       │  │
  │  └────────────────────────────────────┘  │
  │                                          │
  │  保存路径                                 │
  │  ┌───────────────────────────── [浏览] ┐  │
  │  │ D:\我的图片\outlook-export          │  │
  │  └────────────────────────────────────┘  │
  │                                          │
  │                      [取消]  [导出]       │
  └──────────────────────────────────────────┘
"""
from typing import List, Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QRadioButton,
    QButtonGroup, QLineEdit, QFileDialog, QGroupBox, QCheckBox, QMessageBox,
    QSlider, QWidget
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon

import os

def _resource_dir(name: str) -> str:
    bases = [
        getattr(__import__("sys"), "_MEIPASS", None),
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


_ICONS_DIR = _resource_dir("icons")

def _icon(name: str, size: int = 20, color: str | None = None) -> QIcon:
    path = os.path.join(_ICONS_DIR, f"{name}.svg")
    if os.path.exists(path):
        return QIcon(path)
    return QIcon()


# ── 格式常量 ───────────────────────────────────────
FMT_PNG = "png"  # 无损，支持透明
FMT_JPG = "jpg"  # 有损，白底
DEFAULT_JPG_QUALITY = 85  # JPG 默认压缩品质


class ExportFormatDialog(QDialog):
    """
    图片导出格式选择弹窗。
    Returns: (format, keep_alpha, jpg_quality, save_dir) via .get_result()
    """

    def __init__(self, file_paths: List[str], parent=None, initial_save_dir: Optional[str] = None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.format: str = FMT_PNG  # 默认 PNG
        self.keep_alpha: bool = True  # 默认保留透明
        self.jpg_quality: int = DEFAULT_JPG_QUALITY
        self.save_dir: Optional[str] = initial_save_dir if initial_save_dir else None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("图片导出 - 选择格式")
        self.setMinimumSize(540, 460)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        # ── 全局 QGroupBox 样式 ──
        self.setStyleSheet(
            "QGroupBox { border: 1px solid #e7eaef; border-radius: 8px; "
            "margin-top: 14px; padding: 16px 14px 14px 14px; "
            "font-family: Microsoft YaHei, sans-serif; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 14px; "
            "padding: 0 8px; color: #0e1115; font-size: 12px; font-weight: bold; }"
        )

        # ── 1. 文件信息（药丸标签） ──
        file_info = self._summarize_files()
        info_lbl = QLabel(file_info)
        info_lbl.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        info_lbl.setAlignment(Qt.AlignCenter)
        info_lbl.setStyleSheet(
            "color: #0e1115; background: #eff1f4; padding: 10px 16px; "
            "border-radius: 999px; border: 1px solid #e7eaef; font-family: Microsoft YaHei, sans-serif;"
        )
        info_lbl.setWordWrap(True)
        root.addWidget(info_lbl)

        # ── 2. 输出格式选择 ──
        fmt_group = QGroupBox("输出格式")
        fmt_layout = QVBoxLayout(fmt_group)
        fmt_layout.setSpacing(8)

        self.radio_png = QRadioButton(" PNG（无损，支持透明底）")
        self.radio_png.setFont(QFont("Microsoft YaHei", 11))
        self.radio_png.setChecked(True)
        self.radio_png.setCursor(Qt.PointingHandCursor)
        self.radio_png.setToolTip("PNG 格式无损，支持透明背景，文件较大")
        self.radio_png.toggled.connect(self._on_format_changed)

        self.radio_jpg = QRadioButton(" JPG（更小体积，强制白底）")
        self.radio_jpg.setFont(QFont("Microsoft YaHei", 11))
        self.radio_jpg.setCursor(Qt.PointingHandCursor)
        self.radio_jpg.setToolTip("JPG 格式有损压缩，文件小，但不支持透明底（强制白色背景）")
        self.radio_jpg.toggled.connect(self._on_format_changed)

        fmt_layout.addWidget(self.radio_png)
        fmt_layout.addWidget(self.radio_jpg)
        root.addWidget(fmt_group)

        # ── 3. 透明底选项（仅 PNG 有效） ──
        alpha_group = QGroupBox("背景选项")
        alpha_layout = QVBoxLayout(alpha_group)
        alpha_layout.setSpacing(6)

        self.chk_alpha = QCheckBox(" 保留透明底（仅 PNG 格式有效）")
        self.chk_alpha.setFont(QFont("Microsoft YaHei", 10))
        self.chk_alpha.setChecked(True)
        self.chk_alpha.setCursor(Qt.PointingHandCursor)
        self.chk_alpha.setToolTip(
            "勾选：源图透明区域在导出后仍然透明（仅 PNG）\n"
            "不勾选：透明区域填充为白色（适合邮件等场景）"
        )
        self.chk_alpha.setIcon(_icon("check", 18))

        self.alpha_hint = QLabel("当前 PNG 格式，可选透明底")
        self.alpha_hint.setFont(QFont("Microsoft YaHei", 9))
        self.alpha_hint.setStyleSheet("color: #7f8d9f; background: transparent; font-family: Microsoft YaHei, sans-serif; padding-left: 26px;")

        alpha_layout.addWidget(self.chk_alpha)
        alpha_layout.addWidget(self.alpha_hint)
        root.addWidget(alpha_group)

        # ── 4. JPG 压缩品质（仅 JPG 有效） ──
        quality_group = QGroupBox("JPG 品质")
        quality_layout = QVBoxLayout(quality_group)
        quality_layout.setSpacing(8)

        # 滑块行：标签 + 滑块 + 数值
        slider_row = QHBoxLayout()
        slider_row.setSpacing(10)

        self.quality_label = QLabel("品质：")
        self.quality_label.setFont(QFont("Microsoft YaHei", 11))
        self.quality_label.setStyleSheet("color: #333942;")

        self.quality_value = QLabel(f"{self.jpg_quality}%")
        self.quality_value.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        self.quality_value.setFixedWidth(44)
        self.quality_value.setAlignment(Qt.AlignCenter)
        self.quality_value.setStyleSheet(
            "color: #0065fd; background: #eff1f4; border-radius: 6px; "
            "padding: 2px 0; font-family: Microsoft YaHei, sans-serif;"
        )

        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(10, 100)
        self.quality_slider.setValue(self.jpg_quality)
        self.quality_slider.setTickPosition(QSlider.TicksBelow)
        self.quality_slider.setTickInterval(10)
        self.quality_slider.setFixedHeight(28)
        self.quality_slider.setStyleSheet(
            "QSlider::groove:horizontal { background: #e7eaef; height: 6px; border-radius: 3px; }"
            "QSlider::sub-page:horizontal { background: #0065fd; border-radius: 3px; }"
            "QSlider::handle:horizontal { background: #0065fd; width: 18px; height: 18px; "
            "margin: -6px 0; border-radius: 9px; }"
            "QSlider::handle:horizontal:hover { background: #0057da; }"
            "QSlider::tick-mark { width: 1px; height: 6px; background: #d0d5dd; }"
        )
        self.quality_slider.valueChanged.connect(self._on_quality_changed)

        slider_row.addWidget(self.quality_label)
        slider_row.addWidget(self.quality_slider, 1)
        slider_row.addWidget(self.quality_value)
        quality_layout.addLayout(slider_row)

        # 品质说明
        self.quality_hint = QLabel("品质越高文件越大，推荐 75-85%")
        self.quality_hint.setFont(QFont("Microsoft YaHei", 9))
        self.quality_hint.setStyleSheet("color: #7f8d9f; background: transparent; font-family: Microsoft YaHei, sans-serif;")

        quality_layout.addWidget(self.quality_hint)
        root.addWidget(quality_group)

        # 初始状态：PNG 时品质区域禁用
        self._set_quality_enabled(False)

        # ── 5. 保存路径 ──
        save_group = QGroupBox("保存路径")
        save_layout = QHBoxLayout(save_group)
        save_layout.setSpacing(10)

        self.input_save = QLineEdit()
        self.input_save.setPlaceholderText("例如 D:\\我的图片\\outlook-export")
        self.input_save.setFont(QFont("Microsoft YaHei", 10))
        self.input_save.setMinimumHeight(34)
        self.input_save.setStyleSheet(
            "QLineEdit { background: #f9f9fa; color: #0e1115; border: 1px solid #e7eaef; "
            "border-radius: 8px; padding: 0 10px; font-family: Microsoft YaHei, sans-serif; }"
            "QLineEdit:focus { border-color: #557fff; }"
        )
        if self.save_dir:
            self.input_save.setText(self.save_dir)
        save_layout.addWidget(self.input_save, 1)

        btn_browse = QPushButton(" 浏览")
        btn_browse.setFont(QFont("Microsoft YaHei", 10))
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.setIcon(_icon("folder-open", 16))
        btn_browse.setIconSize(QSize(16, 16))
        btn_browse.setFixedHeight(34)
        btn_browse.setStyleSheet(
            "QPushButton { background: #eff1f4; color: #0e1115; border: none; border-radius: 999px; "
            "padding: 0 14px; font-family: Microsoft YaHei, sans-serif; }"
            "QPushButton:hover { background: #dde1e8; }"
        )
        btn_browse.clicked.connect(self._browse_save_dir)
        save_layout.addWidget(btn_browse)

        root.addWidget(save_group)

        # ── 6. 按钮行 ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.setFont(QFont("Microsoft YaHei", 11))
        btn_cancel.setFixedSize(90, 36)
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(
            "QPushButton { background: #eff1f4; color: #0e1115; border: none; border-radius: 999px; "
            "font-family: Microsoft YaHei, sans-serif; }"
            "QPushButton:hover { background: #dde1e8; }"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_ok = QPushButton(" 导出")
        btn_ok.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        btn_ok.setFixedSize(90, 36)
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setIcon(_icon("arrow-down-to-line-white", 18))
        btn_ok.setIconSize(QSize(18, 18))
        btn_ok.setStyleSheet(
            "QPushButton { background: #0065fd; color: white; border: none; border-radius: 999px; "
            "font-family: Microsoft YaHei, sans-serif; }"
            "QPushButton:hover { background: #0057da; }"
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
            return f"已拖入文件：{Path(self.file_paths[0]).name}（{size_str}）"
        return f"已拖入 {n} 个文件（共 {size_str}）"

    def _on_format_changed(self):
        """格式切换：JPG 启用品质滑块 + 禁用透明底，PNG 反之"""
        if self.radio_jpg.isChecked():
            self.chk_alpha.setEnabled(False)
            self.chk_alpha.setChecked(False)
            self.alpha_hint.setText("JPG 格式强制白底，透明底选项已禁用")
            self.alpha_hint.setStyleSheet("color: #ef4444; background: transparent; font-family: Microsoft YaHei, sans-serif; padding-left: 26px;")
            self._set_quality_enabled(True)
        else:
            self.chk_alpha.setEnabled(True)
            self.chk_alpha.setChecked(True)
            self.alpha_hint.setText("当前 PNG 格式，可选透明底")
            self.alpha_hint.setStyleSheet("color: #7f8d9f; background: transparent; font-family: Microsoft YaHei, sans-serif; padding-left: 26px;")
            self._set_quality_enabled(False)

    def _set_quality_enabled(self, enabled: bool):
        """启用/禁用品质滑块区域"""
        self.quality_slider.setEnabled(enabled)
        self.quality_value.setEnabled(enabled)
        self.quality_label.setEnabled(enabled)
        self.quality_hint.setEnabled(enabled)
        if not enabled:
            self.quality_value.setStyleSheet(
                "color: #b0b8c4; background: #f9f9fa; border-radius: 6px; "
                "padding: 2px 0; font-family: Microsoft YaHei, sans-serif;"
            )
            self.quality_hint.setText("选择 JPG 格式后可调整压缩品质")
            self.quality_hint.setStyleSheet("color: #b0b8c4; background: transparent; font-family: Microsoft YaHei, sans-serif;")
        else:
            self.quality_value.setStyleSheet(
                "color: #0065fd; background: #eff1f4; border-radius: 6px; "
                "padding: 2px 0; font-family: Microsoft YaHei, sans-serif;"
            )
            self.quality_hint.setText("品质越高文件越大，推荐 75-85%")
            self.quality_hint.setStyleSheet("color: #7f8d9f; background: transparent; font-family: Microsoft YaHei, sans-serif;")

    def _on_quality_changed(self, value: int):
        self.jpg_quality = value
        self.quality_value.setText(f"{value}%")

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

        # 3. JPG 品质（仅 JPG 有效）
        if self.format == FMT_JPG:
            self.jpg_quality = self.quality_slider.value()

        # 4. 保存路径
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
            "jpg_quality": self.jpg_quality,
            "save_dir": self.save_dir,
            "file_paths": self.file_paths,
        }
