"""Log output panel with download history toggle."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...i18n import t


class LogPanel(QGroupBox):
    def __init__(
        self,
        parent: QWidget | None,
        *,
        on_toggle_history: Callable[[], None],
    ) -> None:
        super().__init__(t("log.title"), parent)
        self._history_visible = False

        root = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addStretch()
        self._history_btn = QPushButton(t("log.show_history"))
        self._history_btn.setFixedWidth(110)
        self._history_btn.clicked.connect(on_toggle_history)
        header.addWidget(self._history_btn)
        root.addLayout(header)

        self._stack = QStackedWidget()
        self._log_text = QPlainTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumBlockCount(500)
        self._history_text = QPlainTextEdit()
        self._history_text.setReadOnly(True)
        self._stack.addWidget(self._log_text)
        self._stack.addWidget(self._history_text)
        root.addWidget(self._stack)

    def log(self, message: str) -> None:
        self._log_text.appendPlainText(message)

    def show_log(self) -> None:
        self._history_visible = False
        self._stack.setCurrentWidget(self._log_text)
        self._history_btn.setText(t("log.show_history"))

    def show_history(self) -> None:
        self._history_visible = True
        self._stack.setCurrentWidget(self._history_text)
        self._history_btn.setText(t("log.show_log"))

    def set_history_text(self, text: str) -> None:
        self._history_text.setPlainText(text)

    def retranslate_ui(self) -> None:
        self.setTitle(t("log.title"))
        if self._history_visible:
            self._history_btn.setText(t("log.show_log"))
        else:
            self._history_btn.setText(t("log.show_history"))
