"""Qt appearance: system/dark/light theme and UI scale from settings."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"


def assets_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"  # type: ignore[attr-defined]
    return _ASSETS_DIR


def load_window_icon() -> QIcon | None:
    for name in ("icon.ico", "icon.png", "icon.icns"):
        path = assets_dir() / name
        if path.is_file():
            return QIcon(str(path))
    return None


def _fusion_standard_palette() -> QPalette:
    """Fresh Fusion light palette (not the app's current palette)."""
    style = QStyleFactory.create("Fusion")
    if style is None:
        return QPalette()
    return style.standardPalette()


def _apply_dark_palette(app: QApplication) -> None:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(127, 127, 127))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(127, 127, 127))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(127, 127, 127))
    app.setPalette(palette)


def _apply_light_palette(app: QApplication) -> None:
    """Explicit Fusion light palette (Windows dark mode won't override)."""
    app.setPalette(_fusion_standard_palette())


def _windows_apps_use_light_theme() -> bool | None:
    """Read Windows 10/11 per-app light theme (AppsUseLightTheme). None if unknown."""
    if sys.platform != "win32":
        return None
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        try:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        finally:
            winreg.CloseKey(key)
        return int(value) == 1
    except OSError:
        return None


def _qt_system_prefers_dark() -> bool | None:
    """Qt 6.5+ OS color scheme. None when not reported (common on Windows)."""
    hints = QApplication.styleHints()
    scheme = hints.colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return True
    if scheme == Qt.ColorScheme.Light:
        return False
    return None


def _system_prefers_dark() -> bool:
    qt = _qt_system_prefers_dark()
    if qt is not None:
        return qt
    win = _windows_apps_use_light_theme()
    if win is not None:
        return not win
    return False


def _resolve_effective_theme(settings: dict[str, Any]) -> str:
    theme = settings.get("theme", "system")
    if theme == "dark":
        return "dark"
    if theme == "light":
        return "light"
    return "dark" if _system_prefers_dark() else "light"


def _set_style_color_scheme(effective: str) -> None:
    hints = QApplication.styleHints()
    if not hasattr(hints, "setColorScheme"):
        return
    if effective == "dark":
        hints.setColorScheme(Qt.ColorScheme.Dark)
    else:
        hints.setColorScheme(Qt.ColorScheme.Light)


def _repolish_widgets(app: QApplication) -> None:
    """Force widgets to pick up the new application palette."""
    style = app.style()
    if style is None:
        return
    for widget in app.allWidgets():
        style.unpolish(widget)
        style.polish(widget)
        widget.update()


def apply_theme(app: QApplication, settings: dict[str, Any]) -> None:
    """Apply theme from settings (system / dark / light)."""
    effective = _resolve_effective_theme(settings)
    user_theme = settings.get("theme", "system")

    # Do not let Windows dark mode override an explicit Light/Dark choice.
    app.setDesktopSettingsAware(user_theme == "system")

    app.setStyle("Fusion")
    _set_style_color_scheme(effective)

    if effective == "dark":
        _apply_dark_palette(app)
    else:
        _apply_light_palette(app)

    _repolish_widgets(app)


def ui_scale_factor(settings: dict[str, Any]) -> float:
    scale = settings.get("ui_scale", 1.0)
    if not isinstance(scale, (int, float)):
        return 1.0
    return max(0.8, min(1.5, float(scale)))


def apply_ui_scale(app: QApplication, settings: dict[str, Any]) -> None:
    """Scale default application font (80%-150% from settings)."""
    scale = ui_scale_factor(settings)
    if scale == 1.0:
        return
    font = app.font()
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() * scale)
    elif font.pixelSize() > 0:
        font.setPixelSize(int(font.pixelSize() * scale))
    else:
        font.setPointSizeF(10.0 * scale)
    app.setFont(font)
