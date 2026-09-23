"""Visual manual cut-position editor for an existing vertical image stack."""

from pathlib import Path
from typing import List

from PIL import Image
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QCursor, QImage, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from image_slicer import complete_cut_positions

from theme import Theme, fit_window_to_screen
from ui_scaling import ResponsiveDialogMixin


class DraggableCutLine(QGraphicsLineItem):
    """A horizontal line constrained only by neighboring user cut lines."""

    def __init__(self, owner: "CutEditorDialog", scene_width: int, scene_y: float):
        super().__init__(0, 0, scene_width, 0)
        self.owner = owner
        self.setPen(QPen(QColor(Theme.PRIMARY), 3, Qt.DashLine))
        self.setCursor(QCursor(Qt.SizeVerCursor))
        self.setZValue(10)
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setPos(0, scene_y)

    def itemChange(self, change, value):
        if (
            change == QGraphicsItem.ItemPositionChange
            and self.scene() is not None
            and isinstance(value, QPointF)
        ):
            return QPointF(0, self.owner.clamp_scene_y(self, value.y()))
        if change == QGraphicsItem.ItemPositionHasChanged:
            self.owner.update_cut_summary()
        return super().itemChange(change, value)


class CutEditorDialog(ResponsiveDialogMixin, QDialog):
    """Scrollable image preview with draggable horizontal cut lines."""

    MIN_SLICE_HEIGHT = 80

    def __init__(
        self,
        slice_paths: List[str],
        max_slice_height: int = 1200,
        parent=None,
    ):
        super().__init__(parent)
        self.slice_paths = list(slice_paths)
        self.max_slice_height = int(max_slice_height)
        self._images = self._load_images(self.slice_paths)
        self.total_height = sum(image.height for image in self._images)
        self._auto_positions = self._cumulative_positions(self._images)
        self._line_items: List[DraggableCutLine] = []
        self._resolved_positions: List[int] | None = None
        self._scale = 1.0
        self._build_ui()
        fit_window_to_screen(self, (760, 700), (520, 340))
        self._setup_responsive_dialog_scale(760)

    @staticmethod
    def _load_images(paths: List[str]) -> List[Image.Image]:
        if not paths:
            raise ValueError("没有可调整的切片。")
        images = []
        for path in paths:
            with Image.open(path) as image:
                images.append(image.convert("RGB").copy())
        return images

    @staticmethod
    def _cumulative_positions(images: List[Image.Image]) -> List[int]:
        positions = []
        current = 0
        for image in images[:-1]:
            current += image.height
            positions.append(current)
        return positions

    def _combined_preview(self) -> Image.Image:
        width = max(image.width for image in self._images)
        combined = Image.new("RGB", (width, self.total_height), (255, 255, 255))
        current_y = 0
        for image in self._images:
            x = (width - image.width) // 2
            combined.paste(image, (x, current_y))
            current_y += image.height

        self._scale = min(1.0, 620 / width, 8000 / self.total_height)
        preview_size = (
            max(1, round(width * self._scale)),
            max(1, round(self.total_height * self._scale)),
        )
        if preview_size != combined.size:
            combined = combined.resize(preview_size, Image.Resampling.LANCZOS)
        return combined

    @staticmethod
    def _to_qpixmap(image: Image.Image) -> QPixmap:
        rgb = image.convert("RGB")
        data = rgb.tobytes("raw", "RGB")
        qimage = QImage(
            data,
            rgb.width,
            rgb.height,
            rgb.width * 3,
            QImage.Format_RGB888,
        ).copy()
        return QPixmap.fromImage(qimage)

    def _build_ui(self):
        self.setWindowTitle("调整切图位置")
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        title = QLabel("拖动橙色横线，调整图片切开的位置")
        title.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {Theme.TEXT_PRIMARY}; font-family: Microsoft YaHei, sans-serif;")
        root.addWidget(title)

        hint = QLabel(
            f"可自由拖动到任意位置，也可以用上方按钮新增/删除单条切线，每片至少 {self.MIN_SLICE_HEIGHT}px。"
            f"超过 {self.max_slice_height}px 的区间会在应用时自动补充安全切线。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; font-size: 12px; font-family: Microsoft YaHei, sans-serif;")
        root.addWidget(hint)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.btn_add = QPushButton("＋ 新增切线")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setToolTip(
            f"新增一条切线。选中某条线时插到它下方居中处，否则插到最宽的区间中间"
            f"（每片至少 {self.MIN_SLICE_HEIGHT}px）。"
        )
        self.btn_add.clicked.connect(self.add_cut_line)
        toolbar.addWidget(self.btn_add)

        self.btn_remove = QPushButton("－ 删除切线")
        self.btn_remove.setCursor(Qt.PointingHandCursor)
        self.btn_remove.setToolTip("删除当前选中的那条切线。先在预览图上点一下要删除的橙色横线。")
        self.btn_remove.clicked.connect(self.remove_cut_line)
        toolbar.addWidget(self.btn_remove)

        self.btn_reset = QPushButton("恢复自动切线")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self.reset_positions)
        toolbar.addWidget(self.btn_reset)
        toolbar.addStretch()
        root.addLayout(toolbar)

        preview = self._combined_preview()
        self.scene = QGraphicsScene(self)
        self.scene.addItem(QGraphicsPixmapItem(self._to_qpixmap(preview)))
        self.scene.setSceneRect(0, 0, preview.width, preview.height)
        self.scene.selectionChanged.connect(self._sync_action_buttons)

        self.view = QGraphicsView(self.scene)
        self.view.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.view.setStyleSheet(
            f"QGraphicsView {{ background: {Theme.CARD}; border: 1px solid {Theme.BORDER}; "
            "border-radius: 8px; }"
        )
        root.addWidget(self.view, 1)

        for position in self._auto_positions:
            self._append_line(position)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(
            f"color: {Theme.PRIMARY}; background: {Theme.GHOST_BG}; border: 1px solid {Theme.BORDER}; "
            "border-radius: 12px; padding: 7px 10px; font-family: Microsoft YaHei, sans-serif;"
        )
        root.addWidget(self.summary_label)

        actions = QHBoxLayout()
        actions.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("应用切线")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        for btn in buttons.buttons():
            btn.setCursor(Qt.PointingHandCursor)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)
        self.update_cut_summary()
        self._sync_action_buttons()

    def _preview_width(self) -> int:
        return int(self.scene.sceneRect().width())

    def _append_line(self, position: int) -> DraggableCutLine:
        """按原图坐标新建一条切线，并保持 _line_items 自上而下有序。"""
        scene_y = position * self._scale
        line = DraggableCutLine(self, self._preview_width(), scene_y)
        self.scene.addItem(line)
        for index, existing in enumerate(self._line_items):
            if existing.pos().y() > scene_y:
                self._line_items.insert(index, line)
                break
        else:
            self._line_items.append(line)
        return line

    def _clear_lines(self):
        for line in list(self._line_items):
            self.scene.removeItem(line)
        self._line_items.clear()

    def _selected_line(self) -> "DraggableCutLine | None":
        for item in self.scene.selectedItems():
            if isinstance(item, DraggableCutLine) and item in self._line_items:
                return item
        return None

    def _gap_bounds(self):
        """返回 [(间隙序号, 起始像素, 结束像素), ...]，序号 i 表示第 i 段切片的区间。"""
        positions = self.cut_positions()
        boundaries = [0, *positions, self.total_height]
        return [
            (index, boundaries[index], boundaries[index + 1])
            for index in range(len(boundaries) - 1)
        ]

    def _insert_candidates(self):
        """只有能被一刀切成两个合规切片（各自 >= MIN_SLICE_HEIGHT）的区间才可新增。"""
        return [
            gap for gap in self._gap_bounds()
            if gap[2] - gap[1] >= self.MIN_SLICE_HEIGHT * 2
        ]

    def _resolve_insert_gap(self):
        candidates = self._insert_candidates()
        if not candidates:
            return None
        selected = self._selected_line()
        if selected is not None:
            selected_index = self._line_items.index(selected)
            # 优先插到选中线下方，其次上方，都放不下时退回最宽区间
            for gap_index, lower, upper in candidates:
                if gap_index == selected_index + 1:
                    return (gap_index, lower, upper)
            for gap_index, lower, upper in candidates:
                if gap_index == selected_index:
                    return (gap_index, lower, upper)
        return max(candidates, key=lambda gap: gap[2] - gap[1])

    def add_cut_line(self):
        gap = self._resolve_insert_gap()
        if gap is None:
            QMessageBox.information(
                self,
                "无法新增切线",
                f"已经没有可再切一刀的空间了（每片至少 {self.MIN_SLICE_HEIGHT}px）。",
            )
            return
        _, lower, upper = gap
        self.scene.clearSelection()
        line = self._append_line(lower + (upper - lower) // 2)
        line.setSelected(True)
        self.update_cut_summary()
        self._sync_action_buttons()

    def remove_cut_line(self):
        line = self._selected_line()
        if line is None:
            return
        self._line_items.remove(line)
        self.scene.removeItem(line)
        self.update_cut_summary()
        self._sync_action_buttons()

    def _sync_action_buttons(self):
        if not hasattr(self, "btn_add"):
            return
        self.btn_add.setEnabled(bool(self._insert_candidates()))
        self.btn_remove.setEnabled(
            bool(self._line_items) and self._selected_line() is not None
        )

    def cut_positions(self) -> List[int]:
        return [
            round(line.pos().y() / self._scale)
            for line in self._line_items
        ]

    def clamp_scene_y(self, item: DraggableCutLine, proposed_y: float) -> float:
        if item not in self._line_items:
            return proposed_y
        index = self._line_items.index(item)
        previous = 0 if index == 0 else round(
            self._line_items[index - 1].pos().y() / self._scale
        )
        following = self.total_height if index == len(self._line_items) - 1 else round(
            self._line_items[index + 1].pos().y() / self._scale
        )
        lower = previous + self.MIN_SLICE_HEIGHT
        upper = following - self.MIN_SLICE_HEIGHT
        proposed = round(proposed_y / self._scale)
        clamped = max(lower, min(upper, proposed))
        return clamped * self._scale

    def update_cut_summary(self):
        if not hasattr(self, "summary_label"):
            return
        positions = self.cut_positions()
        boundaries = [0, *positions, self.total_height]
        heights = [
            boundaries[index + 1] - boundaries[index]
            for index in range(len(boundaries) - 1)
        ]
        positions_text = "、".join(f"{position}px" for position in positions) or "无"
        heights_text = " / ".join(f"{height}px" for height in heights)
        self.summary_label.setText(
            f"共 {len(positions)} 条切线　｜　切片高度：{heights_text}\n"
            f"切线位置：{positions_text}"
        )

    def reset_positions(self):
        """恢复为自动切线：用户新增/删除过的切线一并丢弃，重建与自动结果等量的切线。"""
        self.scene.clearSelection()
        self._clear_lines()
        for position in self._auto_positions:
            self._append_line(position)
        self.update_cut_summary()
        self._sync_action_buttons()

    def _accept_if_valid(self):
        try:
            self._resolved_positions = complete_cut_positions(
                self.total_height,
                self.cut_positions(),
                min_height=self.MIN_SLICE_HEIGHT,
                max_height=self.max_slice_height,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "切线位置不可用", str(exc))
            return
        self.accept()

    def get_cut_positions(self) -> List[int]:
        return self._resolved_positions or self.cut_positions()
