"""Tests for main.py entry point."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Generator
from unittest.mock import patch

import pytest

import main as main_module


@pytest.fixture(autouse=True)
def _reset_main_entry_guard() -> Generator[None, None, None]:
    if hasattr(sys, "_yt_dlp_gui_running"):
        delattr(sys, "_yt_dlp_gui_running")  # type: ignore[attr-defined]
    yield
    if hasattr(sys, "_yt_dlp_gui_running"):
        delattr(sys, "_yt_dlp_gui_running")  # type: ignore[attr-defined]


def test_main_invokes_qt_app() -> None:
    with patch("src.qt.app.run_qt_app") as run_qt:
        main_module.main()
        run_qt.assert_called_once()


def test_reload_main_module() -> None:
    importlib.reload(main_module)
