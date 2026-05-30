"""In-app update availability banner."""

from __future__ import annotations

import webbrowser
from collections.abc import Callable

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


class UpdateBanner(QFrame):
    def __init__(
        self,
        parent: QWidget | None,
        message: str,
        url: str,
        *,
        on_dismiss: Callable[[], None],
        download_label: str,
        dismiss_label: str,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("updateBanner")
        self.setStyleSheet(
            "#updateBanner { background-color: #d1ecf1; border-radius: 6px; }"
            "QLabel { color: #0c5460; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        label = QLabel(message)
        label.setWordWrap(True)
        row.addWidget(label, stretch=1)
        dl_btn = QPushButton(download_label)
        dl_btn.clicked.connect(lambda: webbrowser.open(url))
        row.addWidget(dl_btn)
        dismiss_btn = QPushButton(dismiss_label)
        dismiss_btn.clicked.connect(on_dismiss)
        row.addWidget(dismiss_btn)
