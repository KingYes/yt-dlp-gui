"""Qt application entry — creates QApplication and main window."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ..i18n import load_language, t
from ..state import AppState
from .main_window import MainWindow
from .theme import apply_theme, apply_ui_scale, load_window_icon


def run_qt_app(argv: list[str] | None = None) -> None:
    """Start the PySide6 UI."""
    # High-DPI attributes before QApplication construction
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough,
    )

    state = AppState()
    settings = state.settings
    load_language(settings.get("language", "en"))

    qt_app = QApplication(argv if argv is not None else sys.argv)
    qt_app.setApplicationName("yt-dlp-gui")
    qt_app.setOrganizationName("yt-dlp-gui")
    qt_app.setApplicationDisplayName(t("app.title"))

    icon = load_window_icon()
    if icon is not None:
        qt_app.setWindowIcon(icon)

    apply_theme(qt_app, settings)
    apply_ui_scale(qt_app, settings)

    window = MainWindow(state)
    if icon is not None:
        window.setWindowIcon(icon)
    window.show()

    sys.exit(qt_app.exec())
