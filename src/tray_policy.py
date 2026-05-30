"""Tray behavior helpers (no Qt dependency — safe for unit tests and CI)."""


def should_minimize_on_close(*, minimize_to_tray: bool, downloads_active: bool) -> bool:
    """Whether closing the window should hide to the tray instead of quitting."""
    return minimize_to_tray or downloads_active
