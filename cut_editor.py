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

from image_slicer import validate_cut_positions


class DraggableCutLine(QGraphicsLineItem):
    """A horizontal line constrained by neighboring Outlook-safe slices."""

    def __init__(self, owner: "CutEditorDialog", scene_width: int, scene_y: float):
        super().__init__(0, 0, scene_width, 0)
        self.owner = owner
        self.setPen(QPen(QColor("#D83B01"), 3, Qt.DashLine))
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


class CutEditorDialog(QDialog):
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
        self._scale = 1.0
        self._build_ui()

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
        self.resize(720, 680)
        self.setMinimumSize(620, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        title = QLabel("拖动橙色横线，调整图片切开的位置")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #111827;")
        root.addWidget(title)

        hint = QLabel(
            f"防呆保护：每片至少 {self.MIN_SLICE_HEIGHT}px，"
            f"且不超过经典 Outlook 安全上限 {self.max_slice_height}px。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6B7280; font-size: 12px;")
        root.addWidget(hint)

        preview = self._combined_preview()
        self.scene = QGraphicsScene(self)
        self.scene.addItem(QGraphicsPixmapItem(self._to_qpixmap(preview)))
        self.scene.setSceneRect(0, 0, preview.width, preview.height)

        self.view = QGraphicsView(self.scene)
        self.view.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.view.setStyleSheet(
            "QGraphicsView { background: #F8F9FA; border: 1px solid #E1E4E8; "
            "border-radius: 8px; }"
        )
        root.addWidget(self.view, 1)

        for position in self._auto_positions:
            line = DraggableCutLine(
                self,
                preview.width,
                position * self._scale,
            )
            self.scene.addItem(line)
            self._line_items.append(line)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(
            "color: #005A9E; background: #EFF6FF; border: 1px solid #C7E0F4; "
            "border-radius: 6px; padding: 7px 10px;"
        )
        root.addWidget(self.summary_label)

        actions = QHBoxLayout()
        self.btn_reset = QPushButton("恢复自动切线")
        self.btn_reset.clicked.connect(self.reset_positions)
        actions.addWidget(self.btn_reset)
        actions.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("应用切线")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        root.addLayout(actions)
        self.update_cut_summary()

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
        lower = max(
            previous + self.MIN_SLICE_HEIGHT,
            following - self.max_slice_height,
        )
        upper = min(
            following - self.MIN_SLICE_HEIGHT,
            previous + self.max_slice_height,
        )
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
            f"切线位置：{positions_text}　｜　切片高度：{heights_text}"
        )

    def reset_positions(self):
        for line, position in zip(self._line_items, self._auto_positions):
            line.setPos(0, position * self._scale)
        self.update_cut_summary()

    def _accept_if_valid(self):
        try:
            validate_cut_positions(
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
        return self.cut_positions()
