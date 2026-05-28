from collections.abc import Callable
from tkinter import filedialog
from typing import Any

import customtkinter as ctk

from .i18n import get_available_languages, t
from .state import AppState
from .widgets.settings_sections import (
    _BROWSER_LABELS,
    _BROWSERS,
    _THEMES,
    bind_mousewheel,
    build_advanced_section,
    build_appearance_section,
    build_download_section,
    build_network_section,
)


class SettingsWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent: ctk.CTk,
        state: AppState,
        on_theme_changed: Callable[[], None] | None = None,
        on_clipboard_changed: Callable[[bool], None] | None = None,
        on_language_changed: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(t("settings.title"))
        self.geometry("480x640")
        self.minsize(420, 540)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self._state = state
        self._on_theme_changed = on_theme_changed
        self._on_clipboard_changed = on_clipboard_changed
        self._on_language_changed = on_language_changed
        self._settings: dict[str, Any] = dict(state.settings)

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self)
        scroll.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        self._scroll = scroll

        row = 0
        row = build_appearance_section(self, scroll, row)
        row = build_download_section(self, scroll, row)
        row = build_network_section(self, scroll, row)
        build_advanced_section(self, scroll, row)

        bind_mousewheel(scroll)

    # ----------------------------------------------------------- Callbacks

    def _on_theme_change(self, label: str) -> None:
        theme_labels = [t("settings.theme_system"), t("settings.theme_dark"), t("settings.theme_light")]
        idx = theme_labels.index(label) if label in theme_labels else 0
        theme = _THEMES[idx]
        ctk.set_appearance_mode(theme)
        self._state.save_settings(theme=theme)
        if self._on_theme_changed:
            self._on_theme_changed()

    def _on_scale_change(self, value: float) -> None:
        value = round(value, 2)
        ctk.set_widget_scaling(value)
        self._scale_label.configure(text=f"{int(value * 100)}%")
        self._state.save_settings(ui_scale=value)

    def _on_concurrency_change(self, value: float) -> None:
        n = max(1, min(5, round(value)))
        self._concurrency_label.configure(text=str(n))
        self._state.save_settings(max_concurrent_downloads=n)

    def _on_clipboard_toggle(self) -> None:
        enabled = self._clip_var.get()
        self._state.save_settings(clipboard_monitor=enabled)
        if self._on_clipboard_changed:
            self._on_clipboard_changed(enabled)

    def _on_browser_change(self, label: str) -> None:
        idx = _BROWSER_LABELS.index(label) if label in _BROWSER_LABELS else 0
        browser = _BROWSERS[idx]
        self._state.save_settings(browser_cookies=browser)

    def _on_language_change(self, label: str) -> None:
        available = get_available_languages()
        lang_names = [name for _, name in available]
        idx = lang_names.index(label) if label in lang_names else 0
        code = available[idx][0]
        self._state.save_settings(language=code)
        if self._on_language_changed:
            self.destroy()
            self._on_language_changed(code)

    def _on_portable_toggle(self) -> None:
        enabled = self._portable_var.get()
        if enabled:
            self._state.enable_portable_mode()
        else:
            self._state.disable_portable_mode()

    def _browse_cookie_file(self) -> None:
        path = filedialog.askopenfilename(
            title=t("settings.cookie_file_dialog_title"),
            filetypes=[(t("settings.cookie_file_dialog_text"), "*.txt"), (t("settings.cookie_file_dialog_all"), "*.*")],
        )
        if path:
            self._cookie_entry.delete(0, "end")
            self._cookie_entry.insert(0, path)
            self._state.save_settings(cookie_file=path)

    def _save_text_field(self, key: str, entry: ctk.CTkEntry) -> None:
        self._state.save_settings(**{key: entry.get().strip()})

    def _save_bool(self, key: str, var: ctk.BooleanVar) -> None:
        self._state.save_settings(**{key: var.get()})
