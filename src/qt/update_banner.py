"""In-app update availability banner."""

from __future__ import annotations

import webbrowser
from collections.abc import Callable

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from .theme import info_banner_bg, info_banner_fg


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
        bg = info_banner_bg().name()
        fg = info_banner_fg().name()
        self.setStyleSheet(
            f"#updateBanner {{ background-color: {bg}; border-radius: 6px; }}"
            f"QLabel {{ color: {fg}; }}"
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
