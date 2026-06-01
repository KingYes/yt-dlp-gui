"""Tests for download progress helpers."""

from __future__ import annotations

from src.utils import format_bytes, format_eta, format_speed, truncate_filename


class TestProgressFormatting:
    def test_truncate_long_title(self) -> None:
        title = "a" * 80
        assert len(truncate_filename(title, 60)) == 60

    def test_format_bytes(self) -> None:
        assert "MB" in format_bytes(5 * 1024 * 1024) or "MiB" in format_bytes(5 * 1024 * 1024)

    def test_format_speed_none(self) -> None:
        assert format_speed(None) == "-- B/s"

    def test_format_eta_none(self) -> None:
        assert format_eta(None) == "--:--"
