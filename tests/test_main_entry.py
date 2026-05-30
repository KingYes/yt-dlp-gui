"""Tests for main.py entry point."""

from __future__ import annotations

import importlib
from unittest.mock import patch

import main as main_module


def test_main_invokes_qt_app() -> None:
    with patch("src.qt.app.run_qt_app") as run_qt:
        main_module.main()
        run_qt.assert_called_once()


def test_reload_main_module() -> None:
    importlib.reload(main_module)
