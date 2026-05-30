"""Download UI port — decouples DownloadHandler from a specific toolkit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .state import AppState


@dataclass(frozen=True)
class DownloadFormState:
    """Snapshot of form fields needed to start a download."""

    output_dir: str
    format_key: str
    split_chapters: bool
    input_mode: str
    download_section: bool
    section_start: str
    section_end: str
    custom_format_enabled: bool
    custom_format_string: str
    video_format_id: str
    audio_format_id: str
    convert_format: str
    subtitle_mode: str
    subtitle_burn: bool
    progress_view: str


class DownloadContext(Protocol):
    """Port for download orchestration (implemented by QtDownloadContext)."""

    @property
    def state(self) -> AppState:
        """Persistent application state."""
        ...

    @property
    def output_dir(self) -> str:
        ...

    @output_dir.setter
    def output_dir(self, value: str) -> None:
        ...

    def get_form_state(self) -> DownloadFormState:
        """Read current download form values from the UI."""
        ...

    def get_selected_chapters(self) -> list[str] | None:
        ...

    def get_selected_subtitle_langs(self) -> list[str] | None:
        ...

    def get_custom_format_string(self) -> str:
        ...

    def log(self, message: str) -> None:
        ...

    def init_download_items(self, urls: list[str]) -> None:
        ...

    def set_recent_folders(self, folders: list[str]) -> None:
        ...

    def set_download_buttons_active(self, downloading: bool) -> None:
        ...

    def set_open_folder_enabled(self, enabled: bool) -> None:
        ...

    def schedule_process_queue(self) -> None:
        ...

    def refresh_status_bar(self) -> None:
        ...

    def prepare_download(
        self,
        urls: list[str],
        *,
        playlist: bool,
        format_key: str,
        custom_format_enabled: bool,
    ) -> None:
        """Reset session flags and URL list before a batch download."""
        ...

    def save_last_input_from_form(self, urls: list[str], form: DownloadFormState) -> None:
        ...

    def apply_queue_entry_settings(self, entry: dict) -> None:
        ...

    def reset_progress_start(self, *, selected_chapters: bool) -> None:
        ...

    def apply_progress_update(self, data: dict) -> None:
        ...

    def apply_retry_progress(self, data: dict, item_index: int) -> None:
        ...

    def on_item_finished(self, index: int, total: int, error: str | None) -> None:
        ...

    def on_retry_item_finished(self, item_index: int, error: str | None) -> None:
        ...

    def on_download_finished(self, error: str | None) -> None:
        ...

    @property
    def is_playlist_download(self) -> bool:
        ...
