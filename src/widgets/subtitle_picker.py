"""Non-modal subtitle language picker dialog."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from ..i18n import t
from ..layout_utils import _anchor_start, _c, _pad_end, _sticky_start


class SubtitlePickerDialog(ctk.CTkToplevel):
    def __init__(
        self,
        parent: ctk.CTk,
        available_subtitles: dict[str, list[dict]],
        subtitle_vars: dict[str, ctk.BooleanVar],
        select_all_var: ctk.BooleanVar,
        *,
        on_close: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.title(t("format.subtitle_dialog_title"))
        self.geometry("400x350")
        self.minsize(320, 200)
        self.resizable(True, True)

        self._select_all_var = select_all_var
        self._subtitle_vars = subtitle_vars
        self._on_close = on_close

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        header.grid_columnconfigure(_c(0, 1), weight=1)

        ctk.CTkLabel(
            header, text=t("format.subtitle_languages"),
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

        subs = available_subtitles
        row = 0
        if subs["manual"]:
            ctk.CTkLabel(
                scroll, text=t("format.subtitle_manual"),
                font=ctk.CTkFont(size=11, weight="bold"), anchor=_anchor_start(),
            ).grid(row=row, column=0, sticky=_sticky_start(), pady=(2, 2))
            row += 1
            for entry in subs["manual"]:
                code = entry["code"]
                name = entry["name"]
                var = subtitle_vars[code]
                label = f"{name} ({code})" if name != code else code
                ctk.CTkCheckBox(
                    scroll, text=label, variable=var, font=ctk.CTkFont(size=12),
                ).grid(row=row, column=0, sticky=_sticky_start(), pady=1)
                row += 1

        if subs["auto"]:
            ctk.CTkLabel(
                scroll, text=t("format.subtitle_auto"),
                font=ctk.CTkFont(size=11, weight="bold"), anchor=_anchor_start(),
            ).grid(row=row, column=0, sticky=_sticky_start(), pady=(6, 2))
            row += 1
            for entry in subs["auto"]:
                code = entry["code"]
                name = entry["name"]
                key = f"auto:{code}"
                var = subtitle_vars[key]
                label = f"{name} ({code})" if name != code else code
                ctk.CTkCheckBox(
                    scroll, text=label, variable=var, font=ctk.CTkFont(size=12),
                ).grid(row=row, column=0, sticky=_sticky_start(), pady=1)
                row += 1

        self.protocol("WM_DELETE_WINDOW", self._close)

    def _on_select_all(self) -> None:
        select = self._select_all_var.get()
        for var in self._subtitle_vars.values():
            var.set(select)

    def _close(self) -> None:
        self.destroy()
        self._on_close()
