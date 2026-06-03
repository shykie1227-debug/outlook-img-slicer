"""
可点击热区编辑器（V4.6.1 重设计）

产品改进（防呆 + 编辑 + 简化）：
  1. 去掉"按钮文字"输入框 —— 图片本身已含文字，只标可点击区域 + 挂 URL
  2. URL 智能补全：未填协议时自动加 https://
  3. 防呆校验：
     - 未选区域 / 未填 URL / 区域太小 / 重复区域 → 明确提示，不入库
  4. 编辑能力（V4.6.1 新增）：
     - 列表项双击 → 弹编辑对话框（改 URL）
     - 列表项"✎ 改区域" → 画布进入"重选"模式，用户重新拖框
     - "🗑 删除"按钮 → 二次确认后删除

UI 设计（最简路径）：
  ┌──────────────────────────────────────┐
  │  热区编辑：slice_002.png              │
  │  💡 拖动鼠标框选可点击区域 → 填 URL  │
  │  ┌────────────────────────────┐      │
  │  │     [图片，叠加已选区]      │      │
  │  └────────────────────────────┘      │
  │  URL: [____________________]  [✓ 添加]│
  │  选区: x=0 y=0 w=0 h=0              │
  │  ─────────────────────────────       │
  │  已添加（2 个）:                     │
  │   1. 区域 50,30→350,80  https://...  │
  │      [✎ 改URL] [✎ 改区域] [🗑 删除]  │
  │   2. ...                             │
  │                          [完成]      │
  └──────────────────────────────────────┘
"""
from typing import Optional, List, Tuple
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QListWidget, QListWidgetItem, QMessageBox,
    QDialogButtonBox, QInputDialog, QFrame
)
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QMouseEvent, QFont

from clickable_map import HotspotMap, Hotspot


# ── 颜色常量（独立出来便于复用） ──
COLOR_BORDER_IDLE = QColor(5, 150, 105)         # 已有热区：绿色，表示已可点击
COLOR_FILL_IDLE = QColor(16, 185, 129, 70)
COLOR_BORDER_DRAW = QColor(0, 120, 212)         # 正在拖选：蓝色实线
COLOR_FILL_DRAW = QColor(0, 120, 212, 40)
COLOR_BORDER_EDIT = QColor(220, 38, 38)         # 改区域模式：红色实线
COLOR_FILL_EDIT = QColor(220, 38, 38, 40)
COLOR_BAD = QColor(220, 38, 38)                 # 错误态（区域过小/重复）


def _normalize_url(url: str) -> str:
    """自动补全协议；纯域名视为 https。"""
    url = (url or "").strip()
    if not url:
        return url
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url
    return url


def _domain_of(url: str) -> str:
    """从 URL 提取域名，用于列表显示。"""
    try:
        return urlparse(url).netloc or url
    except Exception:
        return url


def _shorten_url(url: str, max_len: int = 46) -> str:
    """列表和画布徽章中显示 URL，过长时中间截断。"""
    url = url or ""
    if len(url) <= max_len:
        return url
    keep = max(8, (max_len - 3) // 2)
    return f"{url[:keep]}...{url[-keep:]}"


class ImageCanvas(QLabel):
    """可拖框选的图片画布，叠加显示已有热区，支持"改区域"模式。"""

    selection_changed = Signal(QRect)  # 拖框选结束时发射

    # 三种模式：正常拖选 / 改区域（红色）/ 不可拖（错误态）
    MODE_DRAW = "draw"
    MODE_EDIT = "edit"

    def __init__(self, image_path: str, actual_size: Tuple[int, int],
                 hotspots: List[Hotspot], parent=None,
                 target_width: int = 800):
        super().__init__(parent)
        self.image_path = image_path
        self.actual_w, self.actual_h = actual_size
        self.hotspots = hotspots
        self.mode = self.MODE_DRAW
        # V4.6.8：可配置 target_width（默认 800）。
        # 画布只设最小尺寸 = target_width，但允许随父容器 resize 缩放图片
        # 这样小窗口下图片也会等比缩小到适合宽度，**不在画布外产生滚动条**
        # 原图高于画布可见区时仅在 Y 方向出现 scroll（QScrollArea 负责）

        self._target_width = target_width
        self.display_w = target_width
        self.display_h = int(self.actual_h * self.display_w / self.actual_w) if self.actual_w else 600
        self.scale = self.display_w / self.actual_w if self.actual_w else 1.0

        src = QPixmap(image_path)
        self.pixmap = src.scaled(
            self.display_w, self.display_h,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.setPixmap(self.pixmap)
        # V4.6.8：删除 setFixedSize，改用 setMinimumSize，让画布能随父容器缩放
        # 注意：setMinimumSize.width 仍然是 display_w，缩小后画布会留空
        self.setMinimumSize(self.display_w, self.display_h)
        self.setStyleSheet("border: 1px solid #D1D5DB; background: #F3F4F6;")

        # 拖框选状态
        self._dragging = False
        self._start = QPoint()
        self._current = QPoint()
        # 改区域模式下：当前正在改哪个热区
        self._editing_index: Optional[int] = None
        # 待确认的新框选（已拖出但未提交到表单）
        self._pending_rect: Optional[QRect] = None

    def set_hotspots(self, hotspots: List[Hotspot]):
        self.hotspots = hotspots
        self.update()

    def set_mode(self, mode: str, editing_index: Optional[int] = None):
        """切换工作模式：draw（默认拖框选）或 edit（改区域，红色高亮当前）"""
        self.mode = mode
        self._editing_index = editing_index
        self._pending_rect = None
        # 改区域模式自动 focus canvas
        if mode == self.MODE_EDIT:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        self.update()

    def clear_pending(self):
        self._pending_rect = None
        self.update()

    def pending_rect(self) -> Optional[QRect]:
        return self._pending_rect

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.LeftButton and self.pixmap.rect().contains(ev.position().toPoint()):
            self._dragging = True
            self._start = ev.position().toPoint()
            self._current = self._start
            self._pending_rect = None
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
            if rect.width() >= 3 and rect.height() >= 3:
                actual_rect = QRect(
                    int(rect.x() / self.scale),
                    int(rect.y() / self.scale),
                    int(rect.width() / self.scale),
                    int(rect.height() / self.scale),
                )
                self._pending_rect = actual_rect
                self.selection_changed.emit(actual_rect)
            self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)
        painter = QPainter(self)

        # 已有热区：绿色虚线 + 可点击徽章
        for idx, h in enumerate(self.hotspots):
            x1 = int(h.x1 * self.scale)
            y1 = int(h.y1 * self.scale)
            x2 = int(h.x2 * self.scale)
            y2 = int(h.y2 * self.scale)
            # 改区域模式下，正在改的那个画红色高亮
            if self.mode == self.MODE_EDIT and idx == self._editing_index:
                pen_color = COLOR_BORDER_EDIT
                fill_color = COLOR_FILL_EDIT
            else:
                pen_color = COLOR_BORDER_IDLE
                fill_color = COLOR_FILL_IDLE
            painter.setPen(QPen(pen_color, 2, Qt.DashLine))
            painter.setBrush(fill_color)
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)
            # 编号徽章
            painter.setPen(QColor(255, 255, 255))
            painter.setBrush(pen_color)
            painter.drawEllipse(x1, y1, 22, 22)
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
            painter.drawText(x1 + 4, y1 + 16, str(idx + 1))
            badge_text = f"可点击 {idx + 1}: {_domain_of(h.url)}"
            painter.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
            metrics = painter.fontMetrics()
            badge_w = min(max(metrics.horizontalAdvance(badge_text) + 12, 84), max(84, x2 - x1))
            badge_h = 22
            badge_x = x1
            badge_y = max(0, y1 - badge_h - 2)
            if badge_y == 0 and y1 < badge_h + 2:
                badge_y = y1 + 2
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(5, 150, 105, 230))
            painter.drawRoundedRect(badge_x, badge_y, badge_w, badge_h, 4, 4)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(badge_x + 6, badge_y + 16, badge_text)

        # 当前拖框选
        if self._dragging:
            rect = QRect(self._start, self._current).normalized()
            color = COLOR_BORDER_EDIT if self.mode == self.MODE_EDIT else COLOR_BORDER_DRAW
            fill = COLOR_FILL_EDIT if self.mode == self.MODE_EDIT else COLOR_FILL_DRAW
            painter.setPen(QPen(color, 2, Qt.SolidLine))
            painter.setBrush(fill)
            painter.drawRect(rect)


class HotspotEditorDialog(QDialog):
    """单张切片的热区编辑对话框（V4.6.1 重设计）。"""

    def __init__(self, slice_path: str, hotspot_map: HotspotMap, parent=None,
                 source_index: float = 0.0):
        super().__init__(parent)
        self.slice_path = slice_path
        self.slice_filename = Path(slice_path).name
        self.hotspot_map = hotspot_map
        # V4.6.7 排序架构：标注时记录该切片的 source_index
        self.source_index = source_index
        # 当前切片热区副本（编辑期间操作副本，关闭时再回写）
        self._current: List[Hotspot] = [
            Hotspot(x1=h.x1, y1=h.y1, x2=h.x2, y2=h.y2,
                    url=h.url, text=h.text, source_index=h.source_index or source_index)
            for h in hotspot_map.get(self.slice_filename)
        ]

        from PIL import Image
        with Image.open(slice_path) as im:
            self.actual_w, self.actual_h = im.size

        self.setWindowTitle(f"热区编辑：{self.slice_filename}")
        # V4.6.8：最小尺寸改为 640x480，原 900x720 在 1366x768 屏上下都超出
        self.setMinimumSize(640, 480)
        self.resize(880, 640)  # 默认尺寸，窗口可继续拖大变小
        self._build_ui()
        # V4.6.8：初始 fit 一次画布宽度（处理小窗口打开场景）
        self._refit_canvas_to_size()
        self._refresh()

    # ── UI 构造 ──────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # ── 顶部新手引导（3 步图示 + 实时状态） ──
        guide = QFrame()
        guide.setStyleSheet(
            "QFrame { background: #EFF6FF; border: 1px solid #BFDBFE; "
            "border-radius: 8px; padding: 10px; }"
        )
        guide_layout = QVBoxLayout(guide)
        guide_layout.setContentsMargins(12, 8, 12, 8)
        guide_layout.setSpacing(4)

        guide_title = QLabel("🎯 3 步添加可点击按钮")
        guide_title.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        guide_title.setStyleSheet("color: #1E3A8A; background: transparent;")
        guide_layout.addWidget(guide_title)

        guide_steps = QLabel(
            "  ① 在上方图片上 <b>按住鼠标左键拖动</b> 框选可点击区域\n"
            "  ② 在下方 <b>URL 框</b> 粘贴或输入链接（自动补 https://）\n"
            "  ③ 点 <b>✓ 添加</b> 按钮，重复 ①②③ 可添加多个"
        )
        guide_steps.setFont(QFont("Microsoft YaHei", 10))
        guide_steps.setStyleSheet("color: #1E40AF; background: transparent;")
        guide_steps.setWordWrap(True)
        guide_layout.addWidget(guide_steps)

        # 状态提示条（用于"添加成功"等实时反馈）
        self.status_label = QLabel("📍 提示：框选区域会自动激活 URL 输入框")
        self.status_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        self.status_label.setStyleSheet(
            "color: #0078D4; background: #DBEAFE; padding: 6px 10px; "
            "border-radius: 4px;"
        )
        guide_layout.addWidget(self.status_label)
        root.addWidget(guide)

        # 图片画布（V4.6.8：高度自适应，不写死）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)  # 改为 True，让画布随滚动区域大小变化
        scroll.setMinimumHeight(220)  # 最小高度，防止窗体拖太小时画布消失
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #E4E7EC; border-radius: 8px; background: #F9FAFB; }"
        )
        # V4.6.8：画布接受“期望宽度”参数，会按这个宽度等比缩放图片
        # 默认为 800（小窗口也能显示完整），画布有 scroll 可在原图超出时滚动
        self.canvas = ImageCanvas(
            self.slice_path, (self.actual_w, self.actual_h), self._current,
            target_width=800
        )
        self.canvas.selection_changed.connect(self._on_selection)
        scroll.setWidget(self.canvas)
        # stretch=1 让画布在窗口 resize 时获取最多空间（与列表争抢）
        root.addWidget(scroll, 1)

        # 输入区：只 URL
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        url_lbl = QLabel("URL:")
        url_lbl.setFont(QFont("Microsoft YaHei", 11))
        url_lbl.setStyleSheet("color: #374151; background: transparent;")
        input_row.addWidget(url_lbl)

        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("https://example.com  (留空协议时自动加 https://)")
        self.input_url.setFixedHeight(34)
        self.input_url.setStyleSheet(
            "QLineEdit { background: white; border: 1px solid #D1D5DB; border-radius: 6px; padding: 0 8px; }"
        )
        self.input_url.returnPressed.connect(self._add_or_update_hotspot)
        input_row.addWidget(self.input_url, 1)

        self.btn_add = QPushButton("✓ 添加")
        self.btn_add.setFixedSize(72, 34)
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setStyleSheet(
            "QPushButton { background: #0078D4; color: white; border: none; border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #2563EB; }"
            "QPushButton:disabled { background: #BFDBFE; color: white; }"
        )
        self.btn_add.clicked.connect(self._add_or_update_hotspot)
        input_row.addWidget(self.btn_add)

        self.btn_cancel_sel = QPushButton("× 清除选区")
        self.btn_cancel_sel.setFixedSize(90, 34)
        self.btn_cancel_sel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel_sel.setStyleSheet(
            "QPushButton { background: #F3F4F6; color: #374151; border: 1px solid #D1D5DB; border-radius: 6px; }"
            "QPushButton:hover { background: #E5E7EB; }"
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
        list_lbl = QLabel(f"已添加热区（{len(self._current)} 个）:")
        list_lbl.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        list_lbl.setStyleSheet("color: #111827; background: transparent;")
        self.list_label = list_lbl  # 保存引用以便更新计数
        root.addWidget(list_lbl)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { border: 1px solid #E4E7EC; border-radius: 6px; background: white; }"
            "QListWidget::item { padding: 6px; border-bottom: 1px solid #F3F4F6; }"
            "QListWidget::item:selected { background: #EFF6FF; color: #1E3A8A; }"
        )
        # V4.6.8：删除 setFixedHeight(160)，改为最小高度 + 拉伸比例
        self.list_widget.setMinimumHeight(120)
        # 双击 → 编辑 URL
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        # stretch=1 让列表在窗口 resize 时与画布争抢空间（默认 1:1 分配）
        root.addWidget(self.list_widget, 1)

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

    # ── 窗口尺寸自适应（V4.6.8）──────────────────────────────
    def resizeEvent(self, event):
        """窗口 resize 时，按当前宽度重新计算画布渲染尺寸。"""
        super().resizeEvent(event)
        self._refit_canvas_to_size()

    def _refit_canvas_to_size(self):
        """
        V4.6.8 简化：画布按宽度自适应窗口，高度按原图比例自由伸展。
        长图在 scroll 容器内 Y 方向滚动（与浏览器看长图行为一致），
        但**列表/URL/状态/完成按钮永远固定在底部**（不被画布挤出窗口），
        这是相对 V4.6.7 的核心改进。

        Trade-off 诚实说明：
          长图在小窗口下仍需 scroll Y 滚动——这是物理约束（3000px 图塞进 480px
          窗口必然滚动），无解。若用户希望"不滚动"模式，需 V4.6.9 加
          fit-to-height 切换按钮。
        """
        if not hasattr(self, "canvas") or self.canvas is None:
            return
        from PySide6.QtWidgets import QScrollArea
        # 找画布的父 QScrollArea
        parent = self.canvas.parent()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parent()
        if parent is None:
            return
        viewport_w = max(parent.viewport().width(), 200)
        natural_w = self.canvas._target_width
        # 按宽度自适应（避免横向滚动条）
        # 但不能超过原图实际宽度（避免极窄原图被拉伸到 800px 出现模糊）
        new_w = min(natural_w, viewport_w - 4, self.canvas.actual_w)
        new_h = int(self.canvas.actual_h * new_w / self.canvas.actual_w) if self.canvas.actual_w else 600
        if new_w == self.canvas.display_w and new_h == self.canvas.display_h:
            return
        scale = new_w / self.canvas.actual_w if self.canvas.actual_w else 1.0
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt
        src_pix = QPixmap(self.canvas.image_path)
        self.canvas.pixmap = src_pix.scaled(new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.canvas.setPixmap(self.canvas.pixmap)
        self.canvas.display_w = new_w
        self.canvas.display_h = new_h
        self.canvas.scale = scale
        self.canvas.setMinimumSize(new_w, new_h)
        self.canvas.update()

    # ── 状态机 ──────────────────────────────
    def _on_selection(self, rect: QRect):
        """用户在画布上拖出矩形 → 提示当前选区信息"""
        if self.canvas.mode == ImageCanvas.MODE_EDIT:
            prefix = "✎ 新选区"
        else:
            prefix = "已选区域"
        self.selection_label.setText(
            f"{prefix}: x={rect.x()}, y={rect.y()}, "
            f"w={rect.width()}, h={rect.height()}"
        )
        # V4.6.4：状态条提示
        self._set_status(
            f"📐 已框选 {rect.width()}×{rect.height()}px — 粘贴 URL 后按回车或点 ✓ 添加",
            "info",
        )
        self.input_url.setFocus()
        # 选 URL 框全选便于直接粘贴覆盖
        self.input_url.selectAll()

    def _set_status(self, text: str, kind: str = "info"):
        """更新顶部状态条（替代模态弹窗的非阻塞反馈）"""
        if not hasattr(self, "status_label"):
            return
        colors = {
            "info":    ("#0078D4", "#DBEAFE"),  # 蓝底蓝字
            "success": ("#059669", "#D1FAE5"),  # 绿底绿字
            "warning": ("#D97706", "#FEF3C7"),  # 黄底黄字
            "error":   ("#DC2626", "#FEE2E2"),  # 红底红字
        }
        fg, bg = colors.get(kind, colors["info"])
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {fg}; background: {bg}; padding: 6px 10px; "
            f"border-radius: 4px; font-weight: bold;"
        )

    def _clear_pending(self):
        """清除当前画布选区（不影响已添加的热区）"""
        self.canvas.clear_pending()
        self.canvas.set_mode(ImageCanvas.MODE_DRAW)
        self.selection_label.setText("当前未选择区域")

    def _add_or_update_hotspot(self):
        """
        统一入口：
          - 画布在 draw 模式 → 添加新热区
          - 画布在 edit 模式 → 更新指定 index 的热区
        任何防呆校验失败都通过 QMessageBox 弹窗，不入库。
        """
        pending = self.canvas.pending_rect()
        url = _normalize_url(self.input_url.text())

        # ── 防呆 1：未选区域 ──
        if pending is None:
            QMessageBox.warning(self, "未选择区域", "请先在图片上拖动鼠标框选可点击区域。")
            return

        # 构造临时 Hotspot（不直接入库，交给 HotspotMap.add/update 校验）
        candidate = Hotspot(
            x1=pending.x(), y1=pending.y(),
            x2=pending.x() + pending.width(),
            y2=pending.y() + pending.height(),
            url=url, text="",
            source_index=self.source_index,  # V4.6.7
        )

        if self.canvas.mode == ImageCanvas.MODE_EDIT:
            # 改区域模式
            idx = self.canvas._editing_index
            ok, reason = self.hotspot_map.update(self.slice_filename, idx, candidate)
            if not ok:
                QMessageBox.warning(self, "无法更新", reason)
                return
            self._current = self.hotspot_map.get(self.slice_filename)
            self._after_change(edit_mode_done=True)
            # V4.6.4：状态条反馈（不再弹模态对话框）
            self._set_status(f"✅ 热区 #{idx + 1} 已更新（{len(self._current)} 个）", "success")
        else:
            # 添加模式
            ok, reason = self.hotspot_map.add(self.slice_filename, candidate)
            if not ok:
                QMessageBox.warning(self, "无法添加", reason)
                return
            self._current = self.hotspot_map.get(self.slice_filename)
            self._after_change(edit_mode_done=False)
            # V4.6.4：状态条反馈 + 标记最新热区 + 滚动到列表底部
            new_idx = len(self._current) - 1
            self._set_status(
                f"✅ 已添加热区 #{new_idx + 1}（共 {len(self._current)} 个）— 继续拖选可添加更多",
                "success",
            )
            self._highlight_latest = new_idx

    def _after_change(self, edit_mode_done: bool):
        """添加/更新后清理状态"""
        self.input_url.clear()
        self.canvas.clear_pending()
        self.canvas.set_mode(ImageCanvas.MODE_DRAW)
        self.selection_label.setText("当前未选择区域")
        self._refresh()
        # 更新按钮文字回「添加」
        self.btn_add.setText("✓ 添加")
        if edit_mode_done:
            self.btn_add.setStyleSheet(
                "QPushButton { background: #0078D4; color: white; border: none; border-radius: 6px; font-weight: bold; }"
                "QPushButton:hover { background: #2563EB; }"
            )

    # ── 列表项操作（编辑/改区域/删除） ─────
    def _on_item_double_clicked(self, item: QListWidgetItem):
        """双击列表项 → 弹编辑对话框改 URL"""
        idx = item.data(Qt.UserRole)
        if idx is None or not (0 <= idx < len(self._current)):
            return
        h = self._current[idx]
        new_url, ok = QInputDialog.getText(
            self, f"编辑 URL（热区 {idx + 1}）",
            f"当前：{h.url}\n\n新 URL：",
            text=h.url,
        )
        if not ok:
            return
        new_url = _normalize_url(new_url)
        if not new_url:
            QMessageBox.warning(self, "URL 不能为空", "请填写有效的 URL。")
            return
        candidate = Hotspot(x1=h.x1, y1=h.y1, x2=h.x2, y2=h.y2,
                            url=new_url, text=h.text,
                            source_index=h.source_index or self.source_index)
        ok, reason = self.hotspot_map.update(self.slice_filename, idx, candidate)
        if not ok:
            QMessageBox.warning(self, "无法更新", reason)
            return
        self._current = self.hotspot_map.get(self.slice_filename)
        self._refresh()

    def _enter_edit_area_mode(self, idx: int):
        """进入「改区域」模式：用户重拖选区后点击「✓ 更新」完成"""
        if not (0 <= idx < len(self._current)):
            return
        self.canvas.set_mode(ImageCanvas.MODE_EDIT, editing_index=idx)
        self.selection_label.setText(
            f"✎ 改区域模式：正在修改热区 {idx + 1}，请重新拖选新区域后点「✓ 更新」"
        )
        # 改按钮文字和颜色
        self.btn_add.setText("✓ 更新")
        self.btn_add.setStyleSheet(
            "QPushButton { background: #DC2626; color: white; border: none; border-radius: 6px; font-weight: bold; }"
            "QPushButton:hover { background: #B91C1C; }"
        )
        # 清空 URL 输入（用户可能要改 URL）
        self.input_url.setText(self._current[idx].url)
        self.input_url.setFocus()

    def _delete_at(self, idx: int):
        if not (0 <= idx < len(self._current)):
            return
        h = self._current[idx]
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除热区 {idx + 1} 吗？\n区域：{h.x1},{h.y1} → {h.x2},{h.y2}\nURL：{h.url}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.hotspot_map.remove(self.slice_filename, idx)
        self._current = self.hotspot_map.get(self.slice_filename)
        self.canvas.clear_pending()
        self.canvas.set_mode(ImageCanvas.MODE_DRAW)
        self._refresh()

    # ── 刷新列表 ────────────────────────────
    def _refresh(self):
        self.canvas.set_hotspots(self._current)
        self.list_widget.clear()
        for i, h in enumerate(self._current):
            domain = _domain_of(h.url)
            text = (
                f"  ✓ 可点击链接 [{i + 1}]  区域 {h.x1},{h.y1} → {h.x2},{h.y2}  "
                f"({h.x2 - h.x1}×{h.y2 - h.y1}px)\n"
                f"        {domain}  {_shorten_url(h.url)}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, i)
            item.setFont(QFont("Microsoft YaHei", 9))
            item.setSizeHint(item.sizeHint().expandedTo(__import__("PySide6").QtCore.QSize(0, 50)))
            self.list_widget.addItem(item)
        # 更新计数
        self.list_label.setText(f"已添加热区（{len(self._current)} 个）:")
        # 行内按钮
        if self.list_widget.count() > 0 and not hasattr(self, "_inlist_btn_inited"):
            self._inlist_btn_inited = True
            self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
            self.list_widget.customContextMenuRequested.connect(self._on_list_rightclick)

    def _on_list_rightclick(self, pos):
        from PySide6.QtWidgets import QMenu
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        idx = item.data(Qt.UserRole)
        menu = QMenu(self)
        act_url = menu.addAction("✏️ 编辑 URL")
        act_area = menu.addAction("✎ 改区域")
        menu.addSeparator()
        act_del = menu.addAction("🗑 删除")
        chosen = menu.exec(self.list_widget.mapToGlobal(pos))
        if chosen == act_url:
            self._on_item_double_clicked(item)
        elif chosen == act_area:
            self._enter_edit_area_mode(idx)
        elif chosen == act_del:
            self._delete_at(idx)

    # ── 关闭时回写（其实 self._current 已经是 HotspotMap 的引用对象，直接保存即可） ──
    def _save_and_close(self):
        # 编辑过程中 add/update 已经直接写入了 hotspot_map，self._current 只是其引用
        # 但为了防止顺序问题，最后再从 map 同步一次
        self._current = self.hotspot_map.get(self.slice_filename)
        # 如果还有未保存的待选区，提示
        if self.canvas.pending_rect() is not None:
            reply = QMessageBox.question(
                self, "未保存的选区",
                "画布上还有未保存的选区，是否丢弃并关闭？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        self.accept()
