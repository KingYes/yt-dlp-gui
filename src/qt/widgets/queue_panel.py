"""Qt download queue panel."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...i18n import t
from ...utils import truncate_filename


class QueuePanel(QGroupBox):
    def __init__(
        self,
        parent: QWidget | None,
        *,
        on_clear: Callable[[], None],
        on_start: Callable[[], None],
        on_move: Callable[[int, int], None],
        on_remove: Callable[[int], None],
    ) -> None:
        super().__init__(t("queue.title"), parent)
        self._on_move = on_move
        self._on_remove = on_remove

        root = QVBoxLayout(self)
        header = QHBoxLayout()
        self._title = QLabel(t("queue.title"))
        self._title.setStyleSheet("font-weight: bold;")
        header.addWidget(self._title, stretch=1)

        self._clear_btn = QPushButton(t("queue.clear"))
        self._clear_btn.setStyleSheet("background-color: #dc3545;")
        self._clear_btn.clicked.connect(on_clear)
        self._clear_btn.hide()

        self._start_btn = QPushButton(t("queue.start"))
        self._start_btn.setStyleSheet("background-color: #28a745;")
        self._start_btn.clicked.connect(on_start)
        self._start_btn.hide()

        header.addWidget(self._clear_btn)
        header.addWidget(self._start_btn)
        root.addLayout(header)

        self._empty = QLabel(t("queue.empty"))
        self._empty.setStyleSheet("color: gray;")
        root.addWidget(self._empty)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setMaximumHeight(120)
        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._scroll_content)
        self._scroll.hide()
        root.addWidget(self._scroll)

    def rebuild(self, queue: list[dict]) -> None:
        while self._scroll_layout.count():
            layout_item = self._scroll_layout.takeAt(0)
            widget = layout_item.widget() if layout_item is not None else None
            if widget is not None:
                widget.deleteLater()

        if not queue:
            self._title.setText(t("queue.title"))
            self._clear_btn.hide()
            self._start_btn.hide()
            self._scroll.hide()
            self._empty.show()
            return

        self._empty.hide()
        self._title.setText(t("queue.title_count", count=len(queue)))
        self._clear_btn.show()
        self._start_btn.show()
        self._scroll.show()

        for i, entry in enumerate(queue):
            row = QHBoxLayout()
            row_w = QWidget()
            row_w.setLayout(row)

            row.addWidget(QLabel(f"{i + 1}."))

            url_count = len(entry.get("urls", []))
            first_url = truncate_filename(entry["urls"][0], 35) if entry.get("urls") else "?"
            fmt = entry.get("format_key", "Best")
            if url_count == 1:
                display = t("queue.display_single", url=first_url, fmt=fmt)
            else:
                display = t("queue.display_multi", url=first_url, extra=url_count - 1, fmt=fmt)

            title = QLabel(display)
            title.setWordWrap(True)
            row.addWidget(title, stretch=1)

            up_btn = QPushButton("\u25b2")
            up_btn.setFixedSize(28, 22)
            up_btn.setEnabled(i > 0)
            up_btn.clicked.connect(lambda _checked=False, idx=i: self._on_move(idx, -1))
            row.addWidget(up_btn)

            down_btn = QPushButton("\u25bc")
            down_btn.setFixedSize(28, 22)
            down_btn.setEnabled(i < len(queue) - 1)
            down_btn.clicked.connect(lambda _checked=False, idx=i: self._on_move(idx, 1))
            row.addWidget(down_btn)

            remove_btn = QPushButton("\u2715")
            remove_btn.setFixedSize(28, 22)
            remove_btn.setStyleSheet("background-color: #dc3545;")
            remove_btn.clicked.connect(lambda _checked=False, idx=i: self._on_remove(idx))
            row.addWidget(remove_btn)

            self._scroll_layout.addWidget(row_w)

    def retranslate_ui(self, queue_count: int = 0) -> None:
        if queue_count > 0:
            self._title.setText(t("queue.title_count", count=queue_count))
        else:
            self._title.setText(t("queue.title"))
        self._clear_btn.setText(t("queue.clear"))
        self._start_btn.setText(t("queue.start"))
        self._empty.setText(t("queue.empty"))
