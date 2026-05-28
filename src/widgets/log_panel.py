"""Log panel: log textbox and download history toggle."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from ..i18n import t
from ..layout_utils import _anchor_start, _c, _pad_end, _sticky_start


class LogPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkFrame,
        *,
        on_toggle_history: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=8, pady=(8, 0), sticky="ew")
        header.grid_columnconfigure(_c(0, 1), weight=1)

        ctk.CTkLabel(header, text=t("log.title"), font=ctk.CTkFont(size=12, weight="bold"), anchor=_anchor_start()).grid(
            row=0, column=_c(0, 1), sticky=_sticky_start()
        )

        self.history_toggle_btn = ctk.CTkButton(
            header, text=t("log.show_history"), width=100, height=24,
            font=ctk.CTkFont(size=11), command=on_toggle_history,
        )
        self.history_toggle_btn.grid(row=0, column=_c(1, 1), padx=_pad_end(0, 4))

        self.log_box = ctk.CTkTextbox(self, height=100, state="disabled", font=ctk.CTkFont(size=12))
        self.log_box.grid(row=1, column=0, padx=8, pady=(4, 8), sticky="nsew")

        self.history_frame = ctk.CTkFrame(self)
        self.history_textbox = ctk.CTkTextbox(
            self.history_frame, height=100, state="disabled", font=ctk.CTkFont(size=12),
        )
        self.history_textbox.pack(fill="both", expand=True, padx=8, pady=8)

    def log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def show_log(self) -> None:
        self.history_frame.grid_forget()
        self.log_box.grid(row=1, column=0, padx=8, pady=(4, 8), sticky="nsew")
        self.history_toggle_btn.configure(text=t("log.show_history"))

    def show_history(self) -> None:
        self.log_box.grid_forget()
        self.history_frame.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")
        self.history_toggle_btn.configure(text=t("log.show_log"))
