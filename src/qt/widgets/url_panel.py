"""URL input panel (single / multiple modes)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...i18n import t


class UrlPanel(QGroupBox):
    def __init__(
        self,
        parent: QWidget | None,
        *,
        on_download: Callable[[], None],
        on_paste: Callable[[], None],
        on_preview: Callable[[], None],
        on_settings: Callable[[], None],
        on_mode_changed: Callable[[str], None],
        on_url_changed: Callable[[], None],
    ) -> None:
        super().__init__(t("url.label"), parent)
        self._on_mode_changed = on_mode_changed
        self._on_url_changed = on_url_changed
        self._input_mode = "single"

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([t("url.mode_single"), t("url.mode_multiple")])
        self._mode_combo.currentIndexChanged.connect(self._on_mode_combo_changed)
        header.addWidget(self._mode_combo)
        header.addStretch()

        self._settings_btn = QPushButton(t("url.settings"))
        self._settings_btn.clicked.connect(on_settings)
        header.addWidget(self._settings_btn)
        layout.addLayout(header)

        self._single_edit = QLineEdit()
        self._single_edit.setPlaceholderText(t("url.placeholder"))
        self._single_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._single_edit.returnPressed.connect(on_download)
        self._single_edit.textChanged.connect(lambda _text: on_url_changed())

        self._multi_edit = QPlainTextEdit()
        self._multi_edit.setPlaceholderText(t("url.placeholder"))
        self._multi_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._multi_edit.setMaximumHeight(100)
        self._multi_edit.textChanged.connect(on_url_changed)
        self._multi_edit.hide()

        layout.addWidget(self._single_edit)
        layout.addWidget(self._multi_edit)

        actions = QHBoxLayout()
        self._paste_btn = QPushButton(t("url.paste"))
        self._paste_btn.clicked.connect(on_paste)
        actions.addWidget(self._paste_btn)

        self.preview_btn = QPushButton(t("url.preview"))
        self.preview_btn.clicked.connect(on_preview)
        actions.addWidget(self.preview_btn)

        self.preview_label = QLabel("")
        self.preview_label.setWordWrap(True)
        actions.addWidget(self.preview_label, stretch=1)
        layout.addLayout(actions)

    def _on_mode_combo_changed(self, index: int) -> None:
        mode = "multiple" if index == 1 else "single"
        if mode == self._input_mode:
            return
        text = self.get_text()
        self._input_mode = mode
        if mode == "single":
            self._multi_edit.hide()
            self._single_edit.show()
            first = text.splitlines()[0].strip() if text else ""
            self._single_edit.setText(first)
        else:
            self._single_edit.hide()
            self._multi_edit.show()
            self._multi_edit.setPlainText(text)
        self._on_mode_changed(mode)

    def set_mode(self, mode: str) -> None:
        self._input_mode = mode
        label = t("url.mode_multiple") if mode == "multiple" else t("url.mode_single")
        idx = self._mode_combo.findText(label)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        if mode == "single":
            self._multi_edit.hide()
            self._single_edit.show()
        else:
            self._single_edit.hide()
            self._multi_edit.show()

    @property
    def input_mode(self) -> str:
        return self._input_mode

    def get_text(self) -> str:
        if self._input_mode == "single":
            return self._single_edit.text().strip()
        return self._multi_edit.toPlainText().strip()

    def get_urls(self) -> list[str]:
        if self._input_mode == "single":
            raw = self._single_edit.text().strip()
            return [raw] if raw else []
        raw = self._multi_edit.toPlainText().strip()
        if not raw:
            return []
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def set_urls(self, urls: list[str]) -> None:
        if self._input_mode == "single":
            self._single_edit.setText(urls[0] if urls else "")
        else:
            self._multi_edit.setPlainText("\n".join(urls))

    def append_text(self, text: str) -> None:
        if self._input_mode == "single":
            current = self._single_edit.text().strip()
            if current:
                self.set_mode("multiple")
                self._multi_edit.setPlainText(current + "\n" + text)
            else:
                self._single_edit.setText(text)
        else:
            current = self._multi_edit.toPlainText().strip()
            if current:
                self._multi_edit.setPlainText(current + "\n" + text)
            else:
                self._multi_edit.setPlainText(text)

    def set_preview_text(self, text: str, color: str | None = None) -> None:
        self.preview_label.setText(text)
        if color:
            self.preview_label.setStyleSheet(f"color: {color};")

    def set_preview_enabled(self, enabled: bool) -> None:
        self.preview_btn.setEnabled(enabled)

    def focus_text_widget(self) -> QWidget:
        return self._multi_edit if self._input_mode == "multiple" else self._single_edit

    def retranslate_ui(self) -> None:
        self.setTitle(t("url.label"))
        mode = self._input_mode
        self._mode_combo.blockSignals(True)
        self._mode_combo.clear()
        self._mode_combo.addItems([t("url.mode_single"), t("url.mode_multiple")])
        self._mode_combo.setCurrentIndex(1 if mode == "multiple" else 0)
        self._mode_combo.blockSignals(False)
        self._settings_btn.setText(t("url.settings"))
        self._paste_btn.setText(t("url.paste"))
        self.preview_btn.setText(t("url.preview"))
        self._single_edit.setPlaceholderText(t("url.placeholder"))
        self._multi_edit.setPlaceholderText(t("url.placeholder"))
