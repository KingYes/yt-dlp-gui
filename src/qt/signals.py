"""Qt signals for thread-safe UI updates."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class DownloadSignals(QObject):
    """Marshals download callbacks from worker threads to the main Qt thread."""

    progress = Signal(dict)
    item_done = Signal(int, int, object)  # index, total, error str | None
    finished = Signal(object)  # error str | None
    log_message = Signal(str)
