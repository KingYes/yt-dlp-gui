"""Qt subtitle language picker."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...i18n import t


class SubtitlePickerDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        available_subtitles: dict[str, list[dict]],
        subtitle_checks: dict[str, QCheckBox],
        *,
        on_close: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._on_close = on_close
        self._subtitle_checks = subtitle_checks

        self.setWindowTitle(t("format.subtitle_dialog_title"))
        self.setMinimumSize(400, 350)

        layout = QVBoxLayout(self)

        self._select_all = QCheckBox(t("format.select_all"))
        self._select_all.toggled.connect(self._on_select_all)
        layout.addWidget(self._select_all)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        inner = QVBoxLayout(content)

        subs = available_subtitles
        if subs["manual"]:
            inner.addWidget(self._section_label(t("format.subtitle_manual")))
            for entry in subs["manual"]:
                code = entry["code"]
                name = entry["name"]
                label = f"{name} ({code})" if name != code else code
                cb = subtitle_checks[code]
                cb.setText(label)
                inner.addWidget(cb)

        if subs["auto"]:
            inner.addWidget(self._section_label(t("format.subtitle_auto")))
            for entry in subs["auto"]:
                code = entry["code"]
                name = entry["name"]
                key = f"auto:{code}"
                label = f"{name} ({code})" if name != code else code
                cb = subtitle_checks[key]
                cb.setText(label)
                inner.addWidget(cb)

        scroll.setWidget(content)
        layout.addWidget(scroll)

        self.finished.connect(self._handle_close)

    def _section_label(self, text: str) -> QWidget:
        from PySide6.QtWidgets import QLabel

        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; font-size: 11px;")
        return lbl

    def _on_select_all(self, checked: bool) -> None:
        for cb in self._subtitle_checks.values():
            cb.setChecked(checked)

    def _handle_close(self) -> None:
        self._on_close()
