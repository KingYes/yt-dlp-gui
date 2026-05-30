"""Qt clipboard monitoring."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication

from ..i18n import t
from ..utils import is_valid_url

if TYPE_CHECKING:
    from .main_window import MainWindow


class QtClipboardController:
    def __init__(self, window: MainWindow) -> None:
        self._window = window
        self._last = ""
        self._connected = False

    def start(self) -> None:
        if self._connected:
            return
        app = QApplication.instance()
        if app is None:
            return
        clipboard = app.clipboard()
        if clipboard is None:
            return
        self._last = clipboard.text().strip()
        clipboard.dataChanged.connect(self._on_changed)
        self._connected = True

    def stop(self) -> None:
        if not self._connected:
            return
        app = QApplication.instance()
        if app is None:
            self._connected = False
            return
        clipboard = app.clipboard()
        if clipboard is None:
            self._connected = False
            return
        with contextlib.suppress(RuntimeError, TypeError):
            clipboard.dataChanged.disconnect(self._on_changed)
        self._connected = False

    def _on_changed(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        clipboard = app.clipboard()
        if clipboard is None:
            return
        text = clipboard.text().strip()
        if not text or text == self._last or not is_valid_url(text):
            return
        self._last = text
        win = self._window
        existing = win._get_urls()
        if text in existing:
            return
        win._url_panel.append_text(text)
        win._log(t("log.clipboard_added", url=text))
