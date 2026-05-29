"""Queue management: CRUD operations, persistence, and ambiguous-URL dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from .i18n import t
from .utils import truncate_filename

if TYPE_CHECKING:
    from .app import App


class QueueController:
    """Manages the download queue, delegating UI updates back to the App."""

    def __init__(self, app: App) -> None:
        self._app = app

    def build_entry(self, urls: list[str], playlist: bool) -> dict:
        app = self._app
        format_key = app._fmt.format_var.get()
        download_section = app._fmt.section_var.get() and app._input_mode == "single"
        convert_val = app._fmt.convert_var.get()
        sub_val = app._fmt.subtitle_mode_var.get()
        return {
            "urls": urls,
            "playlist": playlist,
            "format_key": format_key,
            "output_dir": app._output_dir,
            "split_chapters": app._fmt.split_chapters_var.get(),
            "custom_format_string": app._get_custom_format_string() if app._custom_format_enabled else "",
            "section_start": app._fmt.section_start_entry.get().strip() if download_section else "",
            "section_end": app._fmt.section_end_entry.get().strip() if download_section else "",
            "convert_format": "" if convert_val == "None" else convert_val.lower(),
            "subtitle_mode": {"Embed": "embed", "File": "file"}.get(sub_val, ""),
            "subtitle_burn": app._fmt.burn_sub_var.get(),
            "selected_chapters": app._get_selected_chapters(),
            "selected_subtitle_langs": app._get_selected_subtitle_langs(),
            "status": "queued",
        }

    def persist(self) -> None:
        app = self._app
        app._state._data["download_queue"] = list(app._queue)
        app._state.save_debounced()

    def update_label(self) -> None:
        count = len(self._app._queue)
        self._app._fmt.queue_label.configure(text=t("queue.label_count", count=count) if count else "")

    def clear(self) -> None:
        app = self._app
        app._queue.clear()
        self.persist()
        self.update_label()
        app._queue_panel.rebuild(app._queue)
        app._log(t("log.queue_cleared"))

    def start(self) -> None:
        app = self._app
        if not app._queue or app._manager.is_busy:
            if app._manager.is_busy:
                app._log(t("log.already_downloading"))
            return
        self.process_next()

    def move_item(self, index: int, direction: int) -> None:
        app = self._app
        new_index = index + direction
        if new_index < 0 or new_index >= len(app._queue):
            return
        app._queue[index], app._queue[new_index] = app._queue[new_index], app._queue[index]
        self.persist()
        app._queue_panel.rebuild(app._queue)

    def remove_item(self, index: int) -> None:
        app = self._app
        if 0 <= index < len(app._queue):
            removed = app._queue.pop(index)
            urls = removed.get("urls", [])
            self.persist()
            self.update_label()
            app._queue_panel.rebuild(app._queue)
            app._log(t("log.removed_from_queue", url=truncate_filename(urls[0], 40) if urls else "?"))

    def process_next(self) -> None:
        app = self._app
        if app._queue and not app._manager.is_busy:
            entry = app._queue.pop(0)
            self.persist()
            self.update_label()
            app._queue_panel.rebuild(app._queue)
            app._dl_handler.start_download_from_entry(entry)

    def show_ambiguous_dialog(self, urls: list[str], ambiguous: list[str]) -> None:
        app = self._app
        dialog = ctk.CTkToplevel(app)
        dialog.title(t("dialog.playlist_title"))
        dialog.geometry("420x150")
        dialog.resizable(False, False)
        dialog.transient(app)
        dialog.grab_set()

        count = len(ambiguous)
        body = t("dialog.playlist_single_url") if count == 1 else t("dialog.playlist_multi_url", count=count)
        ctk.CTkLabel(dialog, text=body, font=ctk.CTkFont(size=13), justify="center").pack(pady=(20, 16))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(0, 12))

        def pick(playlist: bool) -> None:
            dialog.destroy()
            if app._manager.is_busy:
                entry = self.build_entry(urls, playlist)
                app._queue.append(entry)
                self.persist()
                self.update_label()
                app._queue_panel.rebuild(app._queue)
                app._log(t("log.queued_urls_short", count=len(urls)))
            else:
                app._dl_handler.start_download(urls, playlist=playlist)

        ctk.CTkButton(btn_frame, text=t("dialog.single_video_only"), width=160, command=lambda: pick(False)).pack(side="left", padx=8)
        ctk.CTkButton(
            btn_frame, text=t("dialog.entire_playlist"), width=160,
            fg_color="#28a745", hover_color="#218838", command=lambda: pick(True),
        ).pack(side="left", padx=8)
