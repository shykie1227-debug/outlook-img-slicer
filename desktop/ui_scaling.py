"""Shared responsive scaling for secondary desktop dialogs."""

from __future__ import annotations

import re

from PySide6.QtCore import QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QCheckBox, QLayout, QListWidget, QPushButton, QWidget


class ResponsiveDialogMixin:
    """Scale fonts, controls, icons, styles and layouts from stable baselines."""

    def _setup_responsive_dialog_scale(self, reference_width: int) -> None:
        self._scale_reference_width = int(reference_width)
        self._dialog_scale = 1.0
        self._dialog_scale_applying = False
        self._dialog_widget_baselines = {}
        for widget in [self, *self.findChildren(QWidget)]:
            font = widget.font()
            icon_size = widget.iconSize() if isinstance(widget, (QPushButton, QCheckBox)) else None
            style = widget.styleSheet()
            self._dialog_widget_baselines[widget] = {
                "font_size": font.pointSizeF(),
                "minimum": widget.minimumSize(),
                "maximum": widget.maximumSize(),
                "icon_size": icon_size,
                "style": style,
                "last_style": style,
            }

        self._dialog_item_baselines = []
        for list_widget in self.findChildren(QListWidget):
            for index in range(list_widget.count()):
                item = list_widget.item(index)
                self._dialog_item_baselines.append((item, {
                    "font_size": item.font().pointSizeF(),
                    "size_hint": item.sizeHint(),
                }))

        self._dialog_layout_baselines = {}
        for layout in self.findChildren(QLayout):
            margins = layout.contentsMargins()
            self._dialog_layout_baselines[layout] = {
                "margins": (margins.left(), margins.top(), margins.right(), margins.bottom()),
                "spacing": layout.spacing(),
            }
        self._apply_responsive_dialog_scale(self.width(), force=True)

    @staticmethod
    def _scale_dialog_stylesheet(style: str, scale: float) -> str:
        def replace(match):
            value = int(match.group(1))
            return f"{value if value <= 1 else max(1, round(value * scale))}px"

        return re.sub(r"(?<![\w.-])(\d+)px", replace, style)

    def _apply_responsive_dialog_scale(self, width: int, force: bool = False) -> None:
        if not hasattr(self, "_dialog_widget_baselines") or self._dialog_scale_applying:
            return
        scale = min(1.35, max(0.82, width / self._scale_reference_width))
        scale = round(scale * 20) / 20
        if not force and scale == self._dialog_scale:
            return

        self._dialog_scale_applying = True
        try:
            self._dialog_scale = scale
            for widget, baseline in self._dialog_widget_baselines.items():
                font_size = baseline["font_size"]
                if font_size > 0:
                    font = widget.font()
                    font.setPointSizeF(max(1.0, font_size * scale))
                    font.setStyleStrategy(
                        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
                    )
                    widget.setFont(font)

                minimum = baseline["minimum"]
                maximum = baseline["maximum"]
                widget.setMinimumSize(
                    round(minimum.width() * scale) if minimum.width() > 0 else 0,
                    round(minimum.height() * scale) if minimum.height() > 0 else 0,
                )
                widget.setMaximumSize(
                    round(maximum.width() * scale) if maximum.width() < 16777215 else 16777215,
                    round(maximum.height() * scale) if maximum.height() < 16777215 else 16777215,
                )

                icon_size = baseline["icon_size"]
                if icon_size is not None and icon_size.width() > 0:
                    widget.setIconSize(QSize(
                        max(1, round(icon_size.width() * scale)),
                        max(1, round(icon_size.height() * scale)),
                    ))

                current_style = widget.styleSheet()
                if current_style != baseline["last_style"]:
                    baseline["style"] = current_style
                style = baseline["style"]
                if style and "px" in style:
                    applied = self._scale_dialog_stylesheet(style, scale)
                    widget.setStyleSheet(applied)
                    baseline["last_style"] = applied

            for layout, baseline in self._dialog_layout_baselines.items():
                left, top, right, bottom = baseline["margins"]
                layout.setContentsMargins(
                    round(left * scale), round(top * scale),
                    round(right * scale), round(bottom * scale),
                )
                if baseline["spacing"] >= 0:
                    layout.setSpacing(max(0, round(baseline["spacing"] * scale)))

            for item, baseline in self._dialog_item_baselines:
                font = item.font()
                font.setPointSizeF(max(1.0, baseline["font_size"] * scale))
                font.setStyleStrategy(
                    QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
                )
                item.setFont(font)
                size_hint = baseline["size_hint"]
                item.setSizeHint(QSize(
                    round(size_hint.width() * scale),
                    round(size_hint.height() * scale),
                ))
        finally:
            self._dialog_scale_applying = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_responsive_dialog_scale(event.size().width())

    def _scaled_dialog_value(self, value: int) -> int:
        return max(1, round(value * getattr(self, "_dialog_scale", 1.0)))
