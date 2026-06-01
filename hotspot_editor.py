"""
可点击热区编辑器（V4.6 新功能）

UI 设计（最易上手路径）：
  ┌──────────────────────────────────────┐
  │  [X] 热区编辑：slice_002.png    [-][□]│
  ├──────────────────────────────────────┤
  │  提示：在图片上拖动鼠标框选按钮位置  │
  │  • 当前已有 N 个按钮                │
  │  • URL: [____________]              │
  │  • 按钮文字: [______]  [✓ 添加] [× 取消]│
  │  ┌────────────────────────────┐      │
  │  │                            │      │
  │  │     [图片，叠加已选框]      │      │
  │  │                            │      │
  │  └────────────────────────────┘      │
  │  已添加按钮列表:                     │
  │    1. "立即购买" → https://... [删除]│
  │    2. "查看详情" → https://... [删除]│
  │                          [关闭]     │
  └──────────────────────────────────────┘

设计要点：
  - 拖框选 → 弹出小输入条（URL + 按钮文字 + 确定/取消）→ 一键添加
  - 已有热区用半透明橙色矩形 + 编号
  - 跨切片独立：每个切片文件对应一组热区
"""
from typing import Optional, List, Tuple
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QWidget, QListWidget, QListWidgetItem, QMessageBox,
    QFrame
)
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QMouseEvent, QFont

from clickable_map import HotspotMap, Hotspot


class ImageCanvas(QLabel):
    """可拖框选的图片画布，叠加显示已有热区。"""
    selection_changed = Signal(QRect)  # 用户拖框选结束时发射

    def __init__(self, image_path: str, actual_size: Tuple[int, int],
                 hotspots: List[Hotspot], parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.actual_w, self.actual_h = actual_size
        self.hotspots = hotspots

        # 原图 + 渲染尺寸（按宽度 800 等比缩放用于编辑）
        self.display_w = 800
        self.display_h = int(self.actual_h * self.display_w / self.actual_w) if self.actual_w else 600
        self.scale = self.display_w / self.actual_w if self.actual_w else 1.0

        # 加载缩放后 pixmap
        src = QPixmap(image_path)
        self.pixmap = src.scaled(
            self.display_w, self.display_h,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        self.setPixmap(self.pixmap)
        self.setFixedSize(self.display_w, self.display_h)
        self.setStyleSheet("border: 1px solid #D1D5DB; background: #F3F4F6;")

        # 拖框选状态
        self._dragging = False
        self._start = QPoint()
        self._current = QPoint()

    def set_hotspots(self, hotspots: List[Hotspot]):
        self.hotspots = hotspots
        self.update()

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.LeftButton and self.pixmap.rect().contains(ev.position().toPoint()):
            self._dragging = True
            self._start = ev.position().toPoint()
            self._current = self._start
            self.update()

    def mouseMoveEvent(self, ev: QMouseEvent):
        if self._dragging:
            self._current = ev.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, ev: QMouseEvent):
        if self._dragging and ev.button() == Qt.LeftButton:
            self._dragging = False
            self._current = ev.position().toPoint()
            rect = QRect(self._start, self._current).normalized()
            if rect.width() > 5 and rect.height() > 5:
                # 转换到原图像素坐标
                actual_rect = QRect(
                    int(rect.x() / self.scale),
                    int(rect.y() / self.scale),
                    int(rect.width() / self.scale),
                    int(rect.height() / self.scale),
                )
                self.selection_changed.emit(actual_rect)
            self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        painter = QPainter(self)
        # 已有热区：橙色半透明矩形
        for idx, h in enumerate(self.hotspots, 1):
            x1 = int(h.x1 * self.scale)
            y1 = int(h.y1 * self.scale)
            x2 = int(h.x2 * self.scale)
            y2 = int(h.y2 * self.scale)
            painter.setPen(QPen(QColor(255, 140, 0), 2, Qt.DashLine))
            painter.setBrush(QColor(255, 140, 0, 60))
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)
            # 编号
            painter.setPen(QColor(255, 255, 255))
            painter.setBrush(QColor(255, 140, 0))
            painter.drawEllipse(x1, y1, 22, 22)
            painter.setPen(QColor(255, 255, 255))
            f = QFont("Microsoft YaHei", 10, QFont.Bold)
            painter.setFont(f)
            painter.drawText(x1 + 4, y1 + 16, str(idx))

        # 当前拖框选：蓝色实线
        if self._dragging:
            rect = QRect(self._start, self._current).normalized()
            painter.setPen(QPen(QColor(0, 120, 212), 2, Qt.SolidLine))
            painter.setBrush(QColor(0, 120, 212, 40))
            painter.drawRect(rect)


class HotspotEditorDialog(QDialog):
    """单张切片的热区编辑对话框。"""

    hotspots_saved = Signal(str, object)  # (slice_filename, HotspotMap)

    def __init__(self, slice_path: str, hotspot_map: HotspotMap, parent=None):
        super().__init__(parent)
        self.slice_path = slice_path
        self.slice_filename = Path(slice_path).name
        self.hotspot_map = hotspot_map
        # 临时编辑的当前切片热区副本
        self._current: List[Hotspot] = list(hotspot_map.get(self.slice_filename))

        from PIL import Image
        with Image.open(slice_path) as im:
            self.actual_w, self.actual_h = im.size

        self.setWindowTitle(f"热区编辑：{self.slice_filename}")
        self.setMinimumSize(900, 700)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # 提示
        tip = QLabel(
            "💡 在图片上拖动鼠标框选按钮位置 → 填写 URL + 按钮文字 → 添加\n"
            "   已有按钮以橙色虚线框显示，编号对应下方列表。"
        )
        tip.setFont(QFont("Microsoft YaHei", 10))
        tip.setStyleSheet("color: #6B7280; background: transparent;")
        tip.setWordWrap(True)
        root.addWidget(tip)

        # 图片画布（带滚动）
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setFixedHeight(360)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #E4E7EC; border-radius: 8px; background: #F9FAFB; }")
        self.canvas = ImageCanvas(self.slice_path, (self.actual_w, self.actual_h), self._current)
        self.canvas.selection_changed.connect(self._on_selection)
        scroll.setWidget(self.canvas)
        root.addWidget(scroll)

        # 输入区
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        url_lbl = QLabel("URL:")
        url_lbl.setFont(QFont("Microsoft YaHei", 11))
        url_lbl.setStyleSheet("color: #374151; background: transparent;")
        input_row.addWidget(url_lbl)

        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("https://example.com")
        self.input_url.setFixedHeight(34)
        self.input_url.setStyleSheet(
            "QLineEdit { background: white; border: 1px solid #D1D5DB; border-radius: 6px; padding: 0 8px; }"
        )
        input_row.addWidget(self.input_url, 2)

        text_lbl = QLabel("按钮文字:")
        text_lbl.setFont(QFont("Microsoft YaHei", 11))
        text_lbl.setStyleSheet("color: #374151; background: transparent;")
        input_row.addWidget(text_lbl)

        self.input_text = QLineEdit()
        self.input_text.setPlaceholderText("立即购买")
        self.input_text.setFixedHeight(34)
        self.input_text.setFixedWidth(140)
        self.input_text.setStyleSheet(
            "QLineEdit { background: white; border: 1px solid #D1D5DB; border-radius: 6px; padding: 0 8px; }"
        )
        input_row.addWidget(self.input_text)

        self.btn_add = QPushButton("✓ 添加")
        self.btn_add.setFixedSize(72, 34)
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setStyleSheet(
            "QPushButton { background: #0078D4; color: white; border: none; border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #2563EB; }"
            "QPushButton:disabled { background: #BFDBFE; }"
        )
        self.btn_add.clicked.connect(self._add_hotspot)
        input_row.addWidget(self.btn_add)

        self.btn_cancel_sel = QPushButton("× 取消框选")
        self.btn_cancel_sel.setFixedSize(90, 34)
        self.btn_cancel_sel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel_sel.setStyleSheet(
            "QPushButton { background: #F3F4F6; color: #374151; border: 1px solid #D1D5DB; border-radius: 6px; }"
        )
        self.btn_cancel_sel.clicked.connect(self._clear_pending)
        input_row.addWidget(self.btn_cancel_sel)

        root.addLayout(input_row)

        # 选区信息
        self.selection_label = QLabel("当前未选择区域")
        self.selection_label.setFont(QFont("Microsoft YaHei", 10))
        self.selection_label.setStyleSheet("color: #6B7280; background: transparent;")
        root.addWidget(self.selection_label)

        # 已添加列表
        list_lbl = QLabel(f"已添加按钮（{len(self._current)} 个）:")
        list_lbl.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        list_lbl.setStyleSheet("color: #111827; background: transparent;")
        root.addWidget(list_lbl)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { border: 1px solid #E4E7EC; border-radius: 6px; background: white; }"
            "QListWidget::item { padding: 6px; border-bottom: 1px solid #F3F4F6; }"
        )
        self.list_widget.setFixedHeight(120)
        root.addWidget(self.list_widget)

        # 底部按钮
        bottom = QHBoxLayout()
        bottom.addStretch()
        self.btn_close = QPushButton("完成")
        self.btn_close.setFixedSize(90, 36)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet(
            "QPushButton { background: #10B981; color: white; border: none; border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #059669; }"
        )
        self.btn_close.clicked.connect(self._save_and_close)
        bottom.addWidget(self.btn_close)
        root.addLayout(bottom)

    def _on_selection(self, rect: QRect):
        self._pending_rect = rect
        self.selection_label.setText(
            f"已选区域: x={rect.x()}, y={rect.y()}, "
            f"w={rect.width()}, h={rect.height()}"
        )
        self.input_url.setFocus()

    def _clear_pending(self):
        self._pending_rect = None
        self.selection_label.setText("当前未选择区域")

    def _add_hotspot(self):
        if not hasattr(self, "_pending_rect") or self._pending_rect is None:
            QMessageBox.warning(self, "未选择区域", "请先在图片上拖动鼠标框选按钮位置。")
            return
        url = self.input_url.text().strip()
        text = self.input_text.text().strip() or "立即查看"
        if not url:
            QMessageBox.warning(self, "URL 不能为空", "请填写按钮要跳转的 URL。")
            return
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "https://" + url

        r = self._pending_rect
        h = Hotspot(
            x1=r.x(), y1=r.y(),
            x2=r.x() + r.width(), y2=r.y() + r.height(),
            text=text, url=url,
        )
        self._current.append(h)
        self.input_url.clear()
        self.input_text.clear()
        self._clear_pending()
        self._refresh()

    def _delete_at(self, row: int):
        if 0 <= row < len(self._current):
            self._current.pop(row)
            self._refresh()

    def _refresh(self):
        self.canvas.set_hotspots(self._current)
        self.list_widget.clear()
        for i, h in enumerate(self._current, 1):
            item = QListWidgetItem(
                f"  [{i}] \"{h.text}\"  →  {h.url}   "
                f"(区域: {h.x1},{h.y1} → {h.x2},{h.y2})"
            )
            item.setData(Qt.UserRole, i - 1)
            item.setFont(QFont("Microsoft YaHei", 10))
            self.list_widget.addItem(item)

        # 自定义删除按钮
        if self.list_widget.count() > 0 and not hasattr(self, "_del_btn_inited"):
            self._del_btn_inited = True
            self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            self.list_widget.customContextMenuRequested.connect(self._on_list_rightclick)

    def _on_list_rightclick(self, pos):
        from PySide6.QtWidgets import QMenu
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        idx = item.data(Qt.UserRole)
        menu = QMenu(self)
        act_del = menu.addAction("🗑 删除该按钮")
        chosen = menu.exec(self.list_widget.mapToGlobal(pos))
        if chosen == act_del:
            self._delete_at(idx)

    def _save_and_close(self):
        # 写回 HotspotMap：先清除该切片所有旧热区，再写入
        # 用 _map 私有 API（HotspotMap 未提供批量替换）
        if self.slice_filename in self.hotspot_map._map:
            self.hotspot_map._map[self.slice_filename] = []
        else:
            self.hotspot_map._map.setdefault(self.slice_filename, [])
        for h in self._current:
            self.hotspot_map.add(self.slice_filename, h)
        self.accept()
