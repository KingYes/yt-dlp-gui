"""Non-modal chapter picker dialog."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from ..i18n import t
from ..layout_utils import _anchor_start, _c, _pad_end, _sticky_start
from ..utils import format_chapter_range


class ChapterPickerDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent: ctk.CTk,
        chapters: list[dict],
        chapter_vars: list[ctk.BooleanVar],
        select_all_var: ctk.BooleanVar,
        *,
        on_close: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.title(t("format.chapter_dialog_title"))
        self.geometry("400x350")
        self.minsize(320, 200)
        self.resizable(True, True)

        self._select_all_var = select_all_var
        self._chapter_vars = chapter_vars
        self._on_close = on_close

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        header.grid_columnconfigure(_c(0, 1), weight=1)

        ctk.CTkLabel(
            header, text=t("format.chapters"),
            font=ctk.CTkFont(size=13, weight="bold"), anchor=_anchor_start(),
        ).grid(row=0, column=_c(0, 1), sticky=_sticky_start())

        ctk.CTkCheckBox(
            header, text=t("format.select_all"),
            variable=self._select_all_var,
            font=ctk.CTkFont(size=11), command=self._on_select_all,
        ).grid(row=0, column=_c(1, 1), padx=_pad_end(0, 8))

        scroll = ctk.CTkScrollableFrame(self)
        scroll.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        for i, ch in enumerate(chapters):
            var = chapter_vars[i]
            time_range = format_chapter_range(ch["start_time"], ch["end_time"])
            label = f"{i + 1}. {ch['title']} ({time_range})"
            ctk.CTkCheckBox(
                scroll, text=label, variable=var, font=ctk.CTkFont(size=12),
            ).grid(row=i, column=0, sticky=_sticky_start(), pady=1)

        self.protocol("WM_DELETE_WINDOW", self._close)

    def _on_select_all(self) -> None:
        select = self._select_all_var.get()
        for var in self._chapter_vars:
            var.set(select)

    def _close(self) -> None:
        self.destroy()
        self._on_close()
