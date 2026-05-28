"""Progress panel: simple/detailed views, per-item tracking."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from ..i18n import t
from ..layout_utils import _anchor_start, _c, _pad_end, _sticky_end, _sticky_start
from ..utils import truncate_filename


class ProgressPanel(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkFrame,
        *,
        on_open_folder: Callable[[], None],
        on_progress_view_toggle: Callable[[str], None],
        on_retry_item: Callable[[int], None],
    ) -> None:
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)

        self._on_retry_item = on_retry_item
        self._progress_view = "simple"
        self._detail_rows: list[dict] = []
        self._download_items: list[dict] = []

        progress_header = ctk.CTkFrame(self, fg_color="transparent")
        progress_header.grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 2), sticky="ew")
        progress_header.grid_columnconfigure(_c(0, 3), weight=1)

        self.overall_label = ctk.CTkLabel(
            progress_header, text="", anchor=_anchor_start(), font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.overall_label.grid(row=0, column=_c(0, 3), sticky=_sticky_start())

        self._progress_view_var = ctk.StringVar(value=t("progress.view_simple"))
        self.progress_view_toggle = ctk.CTkSegmentedButton(
            progress_header, values=[t("progress.view_simple"), t("progress.view_detailed")],
            variable=self._progress_view_var,
            command=on_progress_view_toggle, width=150,
        )

        self.open_folder_btn = ctk.CTkButton(
            progress_header, text=t("progress.open_folder"), width=90,
            state="disabled", command=on_open_folder,
        )
        self.open_folder_btn.grid(row=0, column=_c(3, 3), padx=_pad_end(0, 4))

        # Simple view
        self._simple_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._simple_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        self._simple_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self._simple_frame, text=t("progress.no_video"), anchor=_anchor_start(), font=ctk.CTkFont(size=13)
        )
        self.title_label.grid(row=0, column=0, padx=12, pady=(2, 2), sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(self._simple_frame)
        self.progress_bar.grid(row=1, column=0, padx=12, pady=4, sticky="ew")
        self.progress_bar.set(0)

        self.progress_detail = ctk.CTkLabel(
            self._simple_frame, text=t("progress.initial"), anchor=_anchor_start(), font=ctk.CTkFont(size=12)
        )
        self.progress_detail.grid(row=2, column=0, padx=12, pady=(2, 10), sticky="ew")

        # Detailed view (hidden)
        self._detailed_frame = ctk.CTkScrollableFrame(self, height=150)

    @property
    def progress_view(self) -> str:
        return self._progress_view

    @property
    def progress_view_var(self) -> ctk.StringVar:
        return self._progress_view_var

    @property
    def detail_rows(self) -> list[dict]:
        return self._detail_rows

    @property
    def download_items(self) -> list[dict]:
        return self._download_items

    @download_items.setter
    def download_items(self, value: list[dict]) -> None:
        self._download_items = value

    def switch_view(self, view: str) -> None:
        self._progress_view = view
        label = t("progress.view_detailed") if view == "detailed" else t("progress.view_simple")
        self._progress_view_var.set(label)
        if view == "simple":
            self._detailed_frame.grid_forget()
            self._simple_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        else:
            self._simple_frame.grid_forget()
            self._detailed_frame.grid(row=1, column=0, columnspan=2, padx=12, pady=(2, 10), sticky="nsew")
            self.rebuild_detail_rows()

    def show_toggle(self) -> None:
        self.progress_view_toggle.grid(row=0, column=_c(2, 3), padx=(8, 0))

    def hide_toggle(self) -> None:
        self.progress_view_toggle.grid_forget()

    def rebuild_detail_rows(self) -> None:
        for widget in self._detailed_frame.winfo_children():
            widget.destroy()
        self._detail_rows = []
        self._detailed_frame.grid_columnconfigure(_c(1, 4), weight=1)

        for i, item in enumerate(self._download_items):
            row_frame = ctk.CTkFrame(self._detailed_frame, fg_color="transparent")
            row_frame.grid(row=i, column=0, columnspan=5, sticky="ew", pady=2)
            row_frame.grid_columnconfigure(_c(1, 4), weight=1)

            status_label = ctk.CTkLabel(
                row_frame, text=_status_icon(item["status"]), width=24,
                font=ctk.CTkFont(size=13),
            )
            status_label.grid(row=0, column=_c(0, 4), padx=(4, 4))

            display = item["title"] or truncate_filename(item["url"], 40)
            title_label = ctk.CTkLabel(
                row_frame, text=display, anchor=_anchor_start(),
                font=ctk.CTkFont(size=12),
            )
            title_label.grid(row=0, column=_c(1, 4), sticky="ew", padx=(0, 4))

            bar = ctk.CTkProgressBar(row_frame, width=120, height=12)
            bar.grid(row=0, column=_c(2, 4), padx=(0, 4))
            bar.set(item["progress"])

            info_label = ctk.CTkLabel(
                row_frame, text=_status_text(item), anchor=_sticky_end(),
                font=ctk.CTkFont(size=11), width=60,
            )
            info_label.grid(row=0, column=_c(3, 4), padx=(0, 4))

            retry_btn = ctk.CTkButton(
                row_frame, text=t("progress.retry"), width=50, height=22,
                font=ctk.CTkFont(size=10),
                fg_color="#dc3545", hover_color="#c82333",
                command=lambda idx=i: self._on_retry_item(idx),
            )
            if item["status"] == "failed":
                retry_btn.grid(row=0, column=_c(4, 4), padx=(0, 4))

            self._detail_rows.append({
                "frame": row_frame,
                "status_label": status_label,
                "title_label": title_label,
                "bar": bar,
                "info_label": info_label,
                "retry_btn": retry_btn,
            })

    def update_detail_row(self, index: int) -> None:
        if index >= len(self._detail_rows) or index >= len(self._download_items):
            return
        item = self._download_items[index]
        row = self._detail_rows[index]

        row["status_label"].configure(text=_status_icon(item["status"]))
        display = item["title"] or truncate_filename(item["url"], 40)
        row["title_label"].configure(text=display)
        row["bar"].set(item["progress"])
        row["info_label"].configure(text=_status_text(item))

        if item["status"] == "failed":
            row["retry_btn"].grid(row=0, column=_c(4, 4), padx=(0, 4))
        else:
            row["retry_btn"].grid_forget()


def _status_icon(status: str) -> str:
    return {"queued": "[ ]", "downloading": "[>]", "done": "[v]", "failed": "[x]"}.get(status, "[ ]")


def _status_text(item: dict) -> str:
    status = item["status"]
    if status == "queued":
        return t("progress.status_queued")
    if status == "downloading":
        pct = item["progress"] * 100
        return f"{pct:.0f}%"
    if status == "done":
        return t("progress.status_done")
    if status == "failed":
        return t("progress.status_failed")
    return ""
