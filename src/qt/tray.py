"""System tray icon and minimize-to-tray behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..ffmpeg_utils import send_notification
from ..i18n import t
from ..tray_policy import should_minimize_on_close
from .theme import load_window_icon

if TYPE_CHECKING:
    from .main_window import MainWindow


class TrayController:
    def __init__(self, window: MainWindow) -> None:
        self._window = window
        self._tray: QSystemTrayIcon | None = None
        self._setup()

    def _setup(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = load_window_icon()
        if icon is None:
            return
        self._tray = QSystemTrayIcon(icon, self._window)
        self._tray.setToolTip(t("tray.tooltip"))
        menu = QMenu(self._window)
        show_action = QAction(t("tray.show_window"), self._window)
        show_action.triggered.connect(self._show_window)
        quit_action = QAction(t("tray.quit"), self._window)
        quit_action.triggered.connect(self._window.quit_application)
        menu.addAction(show_action)
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    def retranslate_ui(self) -> None:
        if self._tray is None:
            return
        self._tray.setToolTip(t("tray.tooltip"))
        menu = self._tray.contextMenu()
        if menu is not None and menu.actions():
            actions = menu.actions()
            if len(actions) >= 2:
                actions[0].setText(t("tray.show_window"))
                actions[1].setText(t("tray.quit"))

    def _show_window(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _downloads_active(self) -> bool:
        win = self._window
        return win._manager.is_busy or bool(win._queue)

    def handle_close_event(self) -> bool:
        """Minimize to tray when enabled or downloads are active. Return True if handled."""
        if self._tray is None:
            return False
        minimize = bool(self._window._state.settings.get("minimize_to_tray", False))
        if not should_minimize_on_close(
            minimize_to_tray=minimize,
            downloads_active=self._downloads_active(),
        ):
            return False
        self._window.hide()
        send_notification(t("app.title"), t("notify.minimized"))
        return True

    def quit(self) -> None:
        if self._tray is not None:
            self._tray.hide()
