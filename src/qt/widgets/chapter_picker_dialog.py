"""Qt chapter picker dialog."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...i18n import t
from ...utils import format_chapter_range


class ChapterPickerDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        chapters: list[dict],
        chapter_checks: list[QCheckBox],
        *,
        on_close: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._on_close = on_close
        self._chapter_checks = chapter_checks

        self.setWindowTitle(t("format.chapter_dialog_title"))
        self.setMinimumSize(400, 350)

        layout = QVBoxLayout(self)

        self._select_all = QCheckBox(t("format.select_all"))
        self._select_all.setChecked(all(cb.isChecked() for cb in chapter_checks))
        self._select_all.toggled.connect(self._on_select_all)
        layout.addWidget(self._select_all)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        inner = QVBoxLayout(content)

        for i, ch in enumerate(chapters):
            time_range = format_chapter_range(ch["start_time"], ch["end_time"])
            label = f"{i + 1}. {ch['title']} ({time_range})"
            chapter_checks[i].setText(label)
            inner.addWidget(chapter_checks[i])

        scroll.setWidget(content)
        layout.addWidget(scroll)

        self.finished.connect(self._handle_close)

    def _on_select_all(self, checked: bool) -> None:
        for cb in self._chapter_checks:
            cb.setChecked(checked)

    def _handle_close(self) -> None:
        self._on_close()
