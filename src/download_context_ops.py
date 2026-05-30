"""Shared DownloadContext operations for Qt and CustomTkinter hosts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .download_progress import (
    DownloadUIHost,
    apply_progress_update,
    apply_retry_progress,
    on_download_finished,
    on_item_finished,
    on_retry_item_finished,
    reset_progress_bar,
)
from .download_session import DownloadSession
from .format_parser import is_audio_only_format

if TYPE_CHECKING:
    from .download_context import DownloadFormState


def prepare_download(
    host: DownloadUIHost,
    urls: list[str],
    *,
    playlist: bool,
    format_key: str,
    custom_format_enabled: bool,
) -> None:
    session = host._download_session
    session.is_playlist_download = playlist
    session.is_audio_download = is_audio_only_format(format_key) and not custom_format_enabled
    session.accumulated_bytes = 0
    session.current_urls = list(urls)
    session.video_title = ""
    session.current_item_index = 0


def save_last_input_from_form(host: DownloadUIHost, urls: list[str], form: DownloadFormState) -> None:
    host._state.save_last_input(
        urls,
        form.output_dir,
        form.format_key,
        form.split_chapters,
        input_mode=form.input_mode,
        progress_view=form.progress_view,
        download_section=form.download_section,
        section_start=form.section_start,
        section_end=form.section_end,
        custom_format_enabled=form.custom_format_enabled,
        video_format_id=form.video_format_id,
        audio_format_id=form.audio_format_id,
    )
    host._state.add_recent_folder(form.output_dir)


def apply_queue_entry_settings(host: DownloadUIHost, entry: dict) -> None:
    if "convert_format" not in entry:
        return
    host._state.save_settings(
        convert_format=entry.get("convert_format", ""),
        subtitle_mode=entry.get("subtitle_mode", ""),
        subtitle_burn=entry.get("subtitle_burn", False),
    )


def sync_session_input_mode(host: DownloadUIHost, input_mode: str) -> None:
    host._download_session.input_mode = input_mode


def init_download_items(host: Any, urls: list[str], input_mode: str) -> None:
    """Initialize progress rows and session counters."""
    sync_session_input_mode(host, input_mode)
    host._init_download_items(urls)
