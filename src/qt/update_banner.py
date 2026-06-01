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
        on_install: Callable[[], None] | None = None,
        install_label: str | None = None,
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
        action_btn = QPushButton(install_label if on_install and install_label else download_label)
        if on_install is not None:
            action_btn.clicked.connect(on_install)
        else:
            action_btn.clicked.connect(lambda: webbrowser.open(url))
        row.addWidget(action_btn)
        dismiss_btn = QPushButton(dismiss_label)
        dismiss_btn.clicked.connect(on_dismiss)
        row.addWidget(dismiss_btn)
