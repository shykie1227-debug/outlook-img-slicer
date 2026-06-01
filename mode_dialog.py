"""
处理模式选择弹窗（V4.6.2 新增）

拖入文件后弹出，让用户选择：
  1. 处理模式：切图模式（默认）/ 图片导出
  2. 保存路径（可选项）
  3. 排序方式（仅多文件时显示）

设计目标：
  - 向后兼容：默认「切图模式」= V4.6.1 工作流
  - 防呆：必选模式才能确定；保存路径只在选择时校验
  - 灵活：用户可跳过保存路径选择（用临时目录）

UI 示意：
  ┌──────────────────────────────────────┐
  │ 📄 已拖入 3 个文件（共 5.2MB）       │
  │                                      │
  │ 处理方式:                             │
  │   (●) ✂️ 切图模式（默认，发送 Outlook）│
  │   ( ) 🖼️ 图片导出（合并为单张长图）   │
  │                                      │
  │ 排序方式（仅多文件时显示）:           │
  │   [文件名自然排序 ▼]                 │
  │                                      │
  │ 保存路径（可选，留空用临时目录）:     │
  │   [_______________________________]   │
  │   [浏览...]                           │
  │                                      │
  │            [确定]  [取消]             │
  └──────────────────────────────────────┘
"""
from typing import List, Optional
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QRadioButton,
    QButtonGroup, QLineEdit, QFileDialog, QGroupBox, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

import os


# ── 模式常量 ───────────────────────────────────────
MODE_SLICE = "slice"        # 切图模式（默认，V4.6.1 行为）
MODE_EXPORT = "export"      # 图片导出模式（新）

# 排序方式
SORT_NATURAL = "natural"    # 文件名自然排序（默认）
SORT_DRAG_ORDER = "drag"    # 拖入顺序


class ProcessModeDialog(QDialog):
    """
    拖入文件后的处理模式选择弹窗。
    Returns: (mode, sort_mode, save_dir) via .result() 或属性访问
    """

    def __init__(self, file_paths: List[str], parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.mode: str = MODE_SLICE  # 默认切图模式
        self.sort_mode: str = SORT_NATURAL  # 默认文件名排序
        self.save_dir: Optional[str] = None  # None = 临时目录
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("选择处理方式")
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

        # ── 2. 处理方式（radio） ──
        mode_group = QGroupBox("处理方式")
        mode_group.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(6)

        self.radio_slice = QRadioButton("✂️  切图模式（默认 — 切成多片，发送 Outlook）")
        self.radio_slice.setFont(QFont("Microsoft YaHei", 11))
        self.radio_slice.setChecked(True)  # 默认勾选
        self.radio_slice.setToolTip("V4.6.1 行为：将长图切成多片，适合插入 Outlook 邮件")

        self.radio_export = QRadioButton("🖼️  图片导出（合并/转换为单张长图）")
        self.radio_export.setFont(QFont("Microsoft YaHei", 11))
        self.radio_export.setToolTip("将多张图片合并为一张长图，或把 PDF/PPT/PSD 转换后的单图保存到本地")

        mode_layout.addWidget(self.radio_slice)
        mode_layout.addWidget(self.radio_export)
        root.addWidget(mode_group)

        # ── 3. 排序方式（仅多文件时显示） ──
        self.sort_widget = QWidget() if False else QGroupBox("排序方式")
        self.sort_widget.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        sort_layout = QHBoxLayout(self.sort_widget)

        self.sort_combo = QComboBox()
        self.sort_combo.addItem("📋 文件名自然排序（推荐）", SORT_NATURAL)
        self.sort_combo.addItem("↕️ 拖入顺序（按用户拖入先后）", SORT_DRAG_ORDER)
        self.sort_combo.setFont(QFont("Microsoft YaHei", 10))
        self.sort_combo.setMinimumWidth(280)
        sort_layout.addWidget(self.sort_combo)
        sort_layout.addStretch()
        if len(self.file_paths) > 1:
            root.addWidget(self.sort_widget)
        # 单文件时隐藏（不必要）

        # ── 4. 保存路径（可选） ──
        save_group = QGroupBox("保存路径（可选 — 留空则存到系统临时目录）")
        save_group.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        save_layout = QHBoxLayout(save_group)

        self.input_save = QLineEdit()
        self.input_save.setPlaceholderText("例如 D:\\我的图片\\outlook-export")
        self.input_save.setFont(QFont("Microsoft YaHei", 10))
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

        btn_ok = QPushButton("确定")
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
        """生成顶部文件信息条文本"""
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

    def _browse_save_dir(self):
        """浏览按钮：弹出目录选择对话框"""
        current = self.input_save.text().strip()
        start_dir = current if current and os.path.isdir(current) else os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(
            self, "选择保存目录", start_dir
        )
        if chosen:
            self.input_save.setText(chosen)

    def _on_accept(self):
        """确定按钮：收集结果并校验"""
        # 1. 模式
        if self.radio_slice.isChecked():
            self.mode = MODE_SLICE
        else:
            self.mode = MODE_EXPORT

        # 2. 排序
        self.sort_mode = self.sort_combo.currentData()

        # 3. 保存路径
        save_path = self.input_save.text().strip()
        if save_path:
            # 校验路径
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
        else:
            self.save_dir = None  # 用临时目录

        self.accept()

    def get_result(self) -> dict:
        """获取用户选择结果（在 exec() 之后调用）"""
        return {
            "mode": self.mode,
            "sort_mode": self.sort_mode,
            "save_dir": self.save_dir,
            "file_paths": self.file_paths,
        }
