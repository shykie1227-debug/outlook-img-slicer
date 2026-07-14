"""Application theme constants for the desktop UI."""


class Theme:
    """Color palette and style constants used across the desktop application."""

    PRIMARY = "#0065fd"
    PRIMARY_HOVER = "#0057da"
    PRIMARY_ACTIVE = "#0043ad"
    PRIMARY_DISABLED = "#e5e9ff"
    PRIMARY_TEXT = "#ffffff"
    SECONDARY_BG = "#ffffff"
    SECONDARY_HOVER = "#eff1f4"
    SECONDARY_BORDER = "#e7eaef"
    SECONDARY_TEXT = "#0e1115"
    GHOST_BG = "#eff1f4"
    GHOST_HOVER = "#dde1e8"
    GHOST_TEXT = "#0e1115"
    SUCCESS = "#10b981"
    SUCCESS_BG = "#ecfdf5"
    SUCCESS_DARK = "#059669"
    ERROR = "#ef4444"
    ERROR_BG = "#fef2f2"
    WARNING = "#f59e0b"
    WARNING_BG = "#fffbeb"
    BG = "#ffffff"
    CARD = "#f9f9fa"
    CARD_SHADOW = "rgba(0, 0, 0, 0.04)"
    BORDER = "#e7eaef"
    BORDER_HOVER = "#d0d5dd"
    BORDER_FOCUS = "#557fff"
    TEXT_PRIMARY = "#0e1115"
    TEXT_SECONDARY = "#333942"
    TEXT_PLACEHOLDER = "#7f8d9f"
    TEXT_DISABLED = "#b0b8c4"
    TEXT_SELECTED = "#00266b"
    DROPZONE_IDLE_BORDER = "#e7eaef"
    DROPZONE_HOVER_BG = "#e5e9ff"
    DROPZONE_HOVER_BORDER = "#0065fd"


def fit_window_to_screen(window, preferred: tuple[int, int], minimum: tuple[int, int]):
    """Keep dialogs operable inside the current screen's logical DPI geometry."""
    from PySide6.QtGui import QGuiApplication

    screen = window.screen() or QGuiApplication.primaryScreen()
    if screen is None:
        window.setMinimumSize(*minimum)
        window.resize(*preferred)
        return
    available = screen.availableGeometry()
    max_width = max(360, available.width() - 32)
    max_height = max(320, available.height() - 32)
    window.setMinimumSize(min(minimum[0], max_width), min(minimum[1], max_height))
    window.resize(min(preferred[0], max_width), min(preferred[1], max_height))
