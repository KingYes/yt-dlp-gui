"""Queue panel: display, reorder, remove queued downloads."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from ..i18n import t
from ..layout_utils import _anchor_start, _c, _sticky_start
from ..utils import truncate_filename


class QueuePanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkFrame,
        *,
        on_clear: Callable[[], None],
        on_start: Callable[[], None],
        on_move: Callable[[int, int], None],
        on_remove: Callable[[int], None],
    ) -> None:
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)

        self._on_move = on_move
        self._on_remove = on_remove

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=12, pady=(8, 4), sticky="ew")
        header.grid_columnconfigure(_c(0, 2), weight=1)

        self.header_label = ctk.CTkLabel(
            header, text=t("queue.title"), font=ctk.CTkFont(size=13, weight="bold"), anchor=_anchor_start(),
        )
        self.header_label.grid(row=0, column=_c(0, 2), sticky=_sticky_start())

        self.clear_btn = ctk.CTkButton(
            header, text=t("queue.clear"), width=60, height=24,
            font=ctk.CTkFont(size=11),
            fg_color="#dc3545", hover_color="#c82333",
            command=on_clear,
        )

        self.start_btn = ctk.CTkButton(
            header, text=t("queue.start"), width=90, height=24,
            font=ctk.CTkFont(size=11),
            fg_color="#28a745", hover_color="#218838",
            command=on_start,
        )

        self.empty_label = ctk.CTkLabel(
            self, text=t("queue.empty"),
            font=ctk.CTkFont(size=12), text_color="gray", anchor=_anchor_start(),
        )
        self.empty_label.grid(row=1, column=0, padx=12, pady=(0, 8), sticky=_sticky_start())

        self._scroll = ctk.CTkScrollableFrame(self, height=100)
        self._scroll.grid_columnconfigure(_c(1, 2), weight=1)

        self._rows: list[dict] = []

    def rebuild(self, queue: list[dict]) -> None:
        for widget in self._scroll.winfo_children():
            widget.destroy()
        self._rows = []

        if not queue:
            self.header_label.configure(text=t("queue.title"))
            self.clear_btn.grid_forget()
            self.start_btn.grid_forget()
            self._scroll.grid_forget()
            self.empty_label.grid(row=1, column=0, padx=12, pady=(0, 8), sticky=_sticky_start())
            return

        self.empty_label.grid_forget()
        self.header_label.configure(text=t("queue.title_count", count=len(queue)))
        self.clear_btn.grid(row=0, column=_c(1, 2), padx=(4, 0))
        self.start_btn.grid(row=0, column=_c(2, 2), padx=(4, 0))
        self._scroll.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")

        for i, entry in enumerate(queue):
            row_frame = ctk.CTkFrame(self._scroll, fg_color="transparent")
            row_frame.grid(row=i, column=0, sticky="ew", pady=2)
            row_frame.grid_columnconfigure(_c(1, 2), weight=1)

            idx_label = ctk.CTkLabel(row_frame, text=f"{i + 1}.", width=24, font=ctk.CTkFont(size=12))
            idx_label.grid(row=0, column=_c(0, 2), padx=(4, 4))

            url_count = len(entry.get("urls", []))
            first_url = truncate_filename(entry["urls"][0], 35) if entry.get("urls") else "?"
            fmt = entry.get("format_key", "Best")
            if url_count == 1:
                display = t("queue.display_single", url=first_url, fmt=fmt)
            else:
                display = t("queue.display_multi", url=first_url, extra=url_count - 1, fmt=fmt)

            title_label = ctk.CTkLabel(
                row_frame, text=display, anchor=_anchor_start(), font=ctk.CTkFont(size=12),
            )
            title_label.grid(row=0, column=_c(1, 2), sticky="ew", padx=(0, 4))

            btn_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            btn_frame.grid(row=0, column=_c(2, 2), padx=(0, 4))

            up_btn = ctk.CTkButton(
                btn_frame, text="\u25B2", width=28, height=22, font=ctk.CTkFont(size=10),
                command=lambda idx=i: self._on_move(idx, -1),
                state="normal" if i > 0 else "disabled",
            )
            up_btn.grid(row=0, column=0, padx=1)

            down_btn = ctk.CTkButton(
                btn_frame, text="\u25BC", width=28, height=22, font=ctk.CTkFont(size=10),
                command=lambda idx=i: self._on_move(idx, 1),
                state="normal" if i < len(queue) - 1 else "disabled",
            )
            down_btn.grid(row=0, column=1, padx=1)

            remove_btn = ctk.CTkButton(
                btn_frame, text="\u2715", width=28, height=22, font=ctk.CTkFont(size=10),
                fg_color="#dc3545", hover_color="#c82333",
                command=lambda idx=i: self._on_remove(idx),
            )
            remove_btn.grid(row=0, column=2, padx=1)

            self._rows.append({
                "frame": row_frame,
                "idx_label": idx_label,
                "title_label": title_label,
                "up_btn": up_btn,
                "down_btn": down_btn,
                "remove_btn": remove_btn,
            })
