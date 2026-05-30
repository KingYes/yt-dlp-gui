"""Qt implementation of DownloadContext."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..download_context import DownloadFormState
from ..download_context_ops import (
    apply_queue_entry_settings,
    init_download_items,
    prepare_download,
    save_last_input_from_form,
)
from ..download_progress import (
    apply_progress_update,
    apply_retry_progress,
    on_download_finished,
    on_item_finished,
    on_retry_item_finished,
    reset_progress_bar,
)
if TYPE_CHECKING:
    from .main_window import MainWindow


class QtDownloadContext:
    def __init__(self, window: MainWindow) -> None:
        self._window = window

    @property
    def state(self) -> object:
        return self._window._state

    @property
    def output_dir(self) -> str:
        return self._window._output_dir

    @output_dir.setter
    def output_dir(self, value: str) -> None:
        self._window._output_dir = value
        self._window._output_panel.set_folders(self._window._state.recent_folders, value)

    @property
    def is_playlist_download(self) -> bool:
        return self._window._download_session.is_playlist_download

    def get_form_state(self) -> DownloadFormState:
        win = self._window
        fmt = win._fmt
        download_section = fmt.section_var.get() and win._input_mode == "single"
        custom_format_str = ""
        video_format_id = ""
        audio_format_id = ""
        if win._custom_format_enabled:
            custom_format_str = win._get_custom_format_string()
            video_label = fmt.video_format_var.get()
            audio_label = fmt.audio_format_var.get()
            for f in win._available_video_formats:
                if f["label"] == video_label:
                    video_format_id = f["format_id"]
                    break
            for f in win._available_audio_formats:
                if f["label"] == audio_label:
                    audio_format_id = f["format_id"]
                    break
        return DownloadFormState(
            output_dir=win._output_dir,
            format_key=fmt.format_var.get(),
            split_chapters=fmt.split_chapters_var.get(),
            input_mode=win._input_mode,
            download_section=download_section,
            section_start=fmt.section_start_entry.get().strip() if download_section else "",
            section_end=fmt.section_end_entry.get().strip() if download_section else "",
            custom_format_enabled=win._custom_format_enabled,
            custom_format_string=custom_format_str,
            video_format_id=video_format_id,
            audio_format_id=audio_format_id,
            convert_format=fmt.convert_var.get(),
            subtitle_mode=fmt.subtitle_mode_var.get(),
            subtitle_burn=fmt.burn_sub_var.get(),
            progress_view=win._progress.progress_view,
        )

    def get_selected_chapters(self) -> list[str] | None:
        return self._window._get_selected_chapters()

    def get_selected_subtitle_langs(self) -> list[str] | None:
        return self._window._get_selected_subtitle_langs()

    def get_custom_format_string(self) -> str:
        return self._window._get_custom_format_string()

    def log(self, message: str) -> None:
        self._window._log(message)

    def init_download_items(self, urls: list[str]) -> None:
        init_download_items(self._window, urls, self._window._input_mode)

    def set_recent_folders(self, folders: list[str]) -> None:
        self._window._folder_menu.configure(values=folders)

    def set_download_buttons_active(self, downloading: bool) -> None:
        if downloading:
            self._window._fmt.download_btn.configure(state="disabled")
            self._window._fmt.cancel_btn.configure(state="normal")
        else:
            self._window._fmt.download_btn.configure(state="normal")
            self._window._fmt.cancel_btn.configure(state="disabled")

    def set_open_folder_enabled(self, enabled: bool) -> None:
        self._window._progress.open_folder_btn.configure(state="normal" if enabled else "disabled")

    def schedule_process_queue(self) -> None:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(100, self._window._process_queue)

    def refresh_status_bar(self) -> None:
        self._window._refresh_status_bar()

    def prepare_download(
        self,
        urls: list[str],
        *,
        playlist: bool,
        format_key: str,
        custom_format_enabled: bool,
    ) -> None:
        prepare_download(
            self._window,
            urls,
            playlist=playlist,
            format_key=format_key,
            custom_format_enabled=custom_format_enabled,
        )

    def save_last_input_from_form(self, urls: list[str], form: DownloadFormState) -> None:
        save_last_input_from_form(self._window, urls, form)

    def apply_queue_entry_settings(self, entry: dict) -> None:
        apply_queue_entry_settings(self._window, entry)

    def reset_progress_start(self, *, selected_chapters: bool) -> None:
        reset_progress_bar(self._window, chapter_mode=selected_chapters)

    def apply_progress_update(self, data: dict) -> None:
        apply_progress_update(self._window, data)

    def apply_retry_progress(self, data: dict, item_index: int) -> None:
        apply_retry_progress(self._window, data, item_index)

    def on_item_finished(self, index: int, total: int, error: str | None) -> None:
        on_item_finished(self._window, index, total, error, refresh_status=self.refresh_status_bar)

    def on_retry_item_finished(self, item_index: int, error: str | None) -> None:
        on_retry_item_finished(self._window, item_index, error, refresh_status=self.refresh_status_bar)

    def on_download_finished(self, error: str | None) -> None:
        on_download_finished(
            self._window,
            error,
            self._window._output_dir,
            log=self.log,
            refresh_status=self.refresh_status_bar,
            schedule_queue=self.schedule_process_queue,
            set_buttons_active=self.set_download_buttons_active,
            set_open_folder_enabled=self.set_open_folder_enabled,
        )
