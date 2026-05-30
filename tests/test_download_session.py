"""Tests for download session and context helpers."""

from __future__ import annotations

from src.download_context_ops import prepare_download
from src.download_session import DownloadSession
from src.format_parser import AUDIO_ONLY_PRESET


class _FakeHost:
    def __init__(self) -> None:
        self._download_session = DownloadSession()
        self._state = None


def test_prepare_download_sets_flags() -> None:
    host = _FakeHost()
    prepare_download(
        host,
        ["https://example.com/watch?v=1"],
        playlist=True,
        format_key=AUDIO_ONLY_PRESET,
        custom_format_enabled=False,
    )
    session = host._download_session
    assert session.is_playlist_download is True
    assert session.is_audio_download is True
    assert session.current_urls == ["https://example.com/watch?v=1"]
    assert session.accumulated_bytes == 0
