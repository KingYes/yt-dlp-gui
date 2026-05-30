"""Tests for tray minimize-on-close logic."""

from __future__ import annotations

from src.qt.tray import TrayController


class TestShouldMinimizeOnClose:
    def test_never_when_disabled_and_idle(self) -> None:
        assert not TrayController.should_minimize_on_close(
            minimize_to_tray=False,
            downloads_active=False,
        )

    def test_when_setting_enabled(self) -> None:
        assert TrayController.should_minimize_on_close(
            minimize_to_tray=True,
            downloads_active=False,
        )

    def test_when_downloads_active(self) -> None:
        assert TrayController.should_minimize_on_close(
            minimize_to_tray=False,
            downloads_active=True,
        )
