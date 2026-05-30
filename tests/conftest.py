"""Pytest configuration — headless Qt for CI and local runs."""

from __future__ import annotations

import os

# Must be set before PySide6 is imported by any test module.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
