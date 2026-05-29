"""Clipboard monitoring and drag-and-drop integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .i18n import t
from .utils import is_valid_url

if TYPE_CHECKING:
    from .app import App

try:
    from tkinterdnd2 import DND_TEXT  # type: ignore[import-untyped]

    _HAS_DND = True
except ImportError:
    _HAS_DND = False


class ClipboardDndController:
    """Manages clipboard monitoring and drag-and-drop for the App."""

    def __init__(self, app: App) -> None:
        self._app = app

    def setup_dnd(self) -> None:
        if not _HAS_DND:
            return
        app = self._app
        try:
            app._url.url_textbox.drop_target_register(DND_TEXT)
            app._url.url_textbox.dnd_bind("<<Drop>>", self._on_dnd_drop)
            app._url.url_entry.drop_target_register(DND_TEXT)
            app._url.url_entry.dnd_bind("<<Drop>>", self._on_dnd_drop)
        except Exception:
            pass

    def _on_dnd_drop(self, event: object) -> None:
        app = self._app
        text = getattr(event, "data", "").strip()
        if not text:
            return
        if app._input_mode == "single" and "\n" in text:
            app._auto_switch_to_multiple(text)
            return
        if app._input_mode == "single":
            app._url.url_entry.delete(0, "end")
            app._url.url_entry.insert(0, text.split("\n")[0].strip())
        else:
            current = app._url.url_textbox.get("1.0", "end").strip()
            if current:
                app._url.url_textbox.insert("end", "\n" + text)
            else:
                app._url.url_textbox.delete("1.0", "end")
                app._url.url_textbox.insert("1.0", text)

    def start_monitor(self) -> None:
        app = self._app
        if app._clipboard_job is not None:
            return
        try:
            app._clipboard_last = app.clipboard_get()
        except Exception:
            app._clipboard_last = ""
        self._poll()

    def stop_monitor(self) -> None:
        app = self._app
        if app._clipboard_job is not None:
            app.after_cancel(app._clipboard_job)
            app._clipboard_job = None

    def _poll(self) -> None:
        app = self._app
        try:
            text = app.clipboard_get().strip()
        except Exception:
            text = ""
        if text and text != app._clipboard_last and is_valid_url(text):
            existing = app._get_urls()
            if text not in existing:
                if app._input_mode == "single":
                    current = app._url.url_entry.get().strip()
                    if current:
                        app._auto_switch_to_multiple(current + "\n" + text)
                    else:
                        app._url.url_entry.delete(0, "end")
                        app._url.url_entry.insert(0, text)
                else:
                    current = app._url.url_textbox.get("1.0", "end").strip()
                    if current:
                        app._url.url_textbox.insert("end", "\n" + text)
                    else:
                        app._url.url_textbox.delete("1.0", "end")
                        app._url.url_textbox.insert("1.0", text)
                app._log(t("log.clipboard_added", url=text))
        app._clipboard_last = text
        app._clipboard_job = app.after(1000, self._poll)
