"""Mutable download session state shared by DownloadHandler and UI hosts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DownloadSession:
    is_playlist_download: bool = False
    is_audio_download: bool = False
    accumulated_bytes: int = 0
    current_urls: list[str] = field(default_factory=list)
    video_title: str = ""
    current_item_index: int = 0
    total_items: int = 0
    input_mode: str = "single"
