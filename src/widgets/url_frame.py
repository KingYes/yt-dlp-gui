"""URL input frame: single/multi entry, paste, preview, mode toggle."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable

import customtkinter as ctk

from ..i18n import t
from ..layout_utils import _anchor_start, _c, _pad_end, _pad_start, _sticky_start

_MACOS = sys.platform == "darwin"


class UrlFrame(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkFrame,
        *,
        on_download: Callable[[], None],
        on_paste: Callable[[], None],
        on_preview: Callable[[], None],
        on_settings: Callable[[], None],
        on_mode_toggle: Callable[[str], None],
        on_url_changed: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)

        self._on_download = on_download
        self._on_mode_toggle = on_mode_toggle
        self._on_url_changed = on_url_changed

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=12, pady=(10, 0), sticky="ew")
        header.grid_columnconfigure(_c(1, 2), weight=1)

        ctk.CTkLabel(header, text=t("url.label"), font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=_c(0, 2), sticky=_sticky_start()
        )

        self._mode_var = ctk.StringVar(value=t("url.mode_single"))
        self._mode_toggle = ctk.CTkSegmentedButton(
            header, values=[t("url.mode_single"), t("url.mode_multiple")], variable=self._mode_var,
            command=on_mode_toggle, width=160,
        )
        self._mode_toggle.grid(row=0, column=_c(1, 2), padx=(8, 0), sticky=_sticky_start())

        self._settings_btn = ctk.CTkButton(
            header, text=t("url.settings"), width=80, command=on_settings,
        )
        self._settings_btn.grid(row=0, column=_c(2, 2), padx=_pad_end(0, 4))

        self.url_entry = ctk.CTkEntry(self, font=ctk.CTkFont(size=13), placeholder_text=t("url.placeholder"))
        self.url_entry.bind("<Return>", lambda _: on_download())
        self._url_debounce_id: str | None = None
        self.url_entry.bind("<KeyRelease>", lambda _: self._debounce_url_changed())

        self.url_textbox = ctk.CTkTextbox(self, height=80, font=ctk.CTkFont(size=13),
                                          undo=True, autoseparators=True, maxundo=-1)
        self.url_textbox.bind("<KeyRelease>", lambda _: self._debounce_url_changed())

        if _MACOS:
            self.url_textbox.bind("<Command-z>", self._on_undo)
            self.url_textbox.bind("<Command-Z>", self._on_redo)
            self.url_textbox.bind("<Command-Shift-z>", self._on_redo)
            self.url_textbox.bind("<Command-Shift-Z>", self._on_redo)
        else:
            self.url_textbox.bind("<Control-Shift-z>", self._on_redo)
            self.url_textbox.bind("<Control-Shift-Z>", self._on_redo)
            self.url_textbox.bind("<Control-y>", self._on_redo)

        self._on_paste_cb = on_paste
        self.url_entry.bind("<<Paste>>", self._on_entry_paste)

        self.url_entry.grid(row=1, column=0, padx=12, pady=(6, 0), sticky="ew")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, padx=12, pady=(6, 0), sticky="ew")
        actions.grid_columnconfigure(_c(2, 2), weight=1)

        self._paste_btn = ctk.CTkButton(actions, text=t("url.paste"), width=70, command=on_paste)
        self._paste_btn.grid(row=0, column=_c(0, 2), padx=_pad_start(0, 4))

        self._preview_btn = ctk.CTkButton(actions, text=t("url.preview"), width=70, command=on_preview)
        self._preview_btn.grid(row=0, column=_c(1, 2))

        self.preview_label = ctk.CTkLabel(
            actions, text="", anchor=_anchor_start(), font=ctk.CTkFont(size=12),
            wraplength=400,
        )
        self.preview_label.grid(row=0, column=_c(2, 2), padx=(8, 0), sticky="ew")

    @property
    def mode_var(self) -> ctk.StringVar:
        return self._mode_var

    @property
    def preview_btn(self) -> ctk.CTkButton:
        return self._preview_btn

    def set_mode(self, label: str) -> None:
        self._mode_var.set(label)

    def _on_entry_paste(self, _event: object = None) -> str | None:
        try:
            text = self.clipboard_get().strip()
        except Exception:
            return None
        if "\n" in text:
            self._on_paste_cb()
            return "break"
        return None

    def _on_undo(self, _event: object = None) -> str:
        with contextlib.suppress(Exception):
            self.url_textbox.edit_undo()
        return "break"

    def _on_redo(self, _event: object = None) -> str:
        with contextlib.suppress(Exception):
            self.url_textbox.edit_redo()
        return "break"

    def _debounce_url_changed(self) -> None:
        if self._url_debounce_id is not None:
            self.after_cancel(self._url_debounce_id)
        self._url_debounce_id = self.after(50, self._fire_url_changed)

    def _fire_url_changed(self) -> None:
        self._url_debounce_id = None
        self._on_url_changed()
