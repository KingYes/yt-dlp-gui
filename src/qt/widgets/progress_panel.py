"""Progress panel with simple and detailed views."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from ...i18n import t
from ...utils import truncate_filename
from ..compat import ButtonCompat, LabelCompat, ProgressBarCompat


class ProgressPanel(QGroupBox):
    def __init__(
        self,
        parent: QWidget | None,
        *,
        on_open_folder: Callable[[], None],
        on_view_changed: Callable[[str], None],
        on_retry_item: Callable[[int], None],
    ) -> None:
        super().__init__(parent)
        self._on_retry_item = on_retry_item
        self._progress_view = "simple"
        self._detail_rows: list[dict] = []
        self._download_items: list[dict] = []

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self._overall = QLabel("")
        font = self._overall.font()
        font.setBold(True)
        self._overall.setFont(font)
        header.addWidget(self._overall, stretch=1)

        self._view_combo = QComboBox()
        self._view_combo.addItems([t("progress.view_simple"), t("progress.view_detailed")])
        self._view_combo.currentTextChanged.connect(self._on_view_combo)
        self._view_combo.hide()
        header.addWidget(self._view_combo)

        self._open_btn = QPushButton(t("progress.open_folder"))
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(on_open_folder)
        header.addWidget(self._open_btn)
        layout.addLayout(header)

        self._simple = QWidget()
        simple_layout = QVBoxLayout(self._simple)
        self._title = QLabel(t("progress.no_video"))
        simple_layout.addWidget(self._title)
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        simple_layout.addWidget(self._bar)
        self._detail = QLabel(t("progress.initial"))
        simple_layout.addWidget(self._detail)
        layout.addWidget(self._simple)

        self._detailed_scroll = QScrollArea()
        self._detailed_scroll.setWidgetResizable(True)
        self._detailed_scroll.setMaximumHeight(180)
        self._detailed_inner = QWidget()
        self._detailed_layout = QVBoxLayout(self._detailed_inner)
        self._detailed_scroll.setWidget(self._detailed_inner)
        self._detailed_scroll.hide()
        layout.addWidget(self._detailed_scroll)

        self.overall_label = LabelCompat(self._overall)
        self.title_label = LabelCompat(self._title)
        self.progress_detail = LabelCompat(self._detail)
        self.progress_bar = ProgressBarCompat(self._bar)
        self.open_folder_btn = ButtonCompat(self._open_btn)
        self.progress_view_toggle = _ViewComboCompat(self._view_combo)

    def _on_view_combo(self, label: str) -> None:
        view = "detailed" if label == t("progress.view_detailed") else "simple"
        self.switch_view(view)

    @property
    def progress_view(self) -> str:
        return self._progress_view

    @property
    def download_items(self) -> list[dict]:
        return self._download_items

    @download_items.setter
    def download_items(self, value: list[dict]) -> None:
        self._download_items = value

    def switch_view(self, view: str) -> None:
        self._progress_view = view
        label = t("progress.view_detailed") if view == "detailed" else t("progress.view_simple")
        idx = self._view_combo.findText(label)
        if idx >= 0:
            self._view_combo.setCurrentIndex(idx)
        if view == "simple":
            self._detailed_scroll.hide()
            self._simple.show()
        else:
            self._simple.hide()
            self._detailed_scroll.show()
            self.rebuild_detail_rows()

    def show_toggle(self) -> None:
        self._view_combo.show()

    def hide_toggle(self) -> None:
        self._view_combo.hide()

    def retranslate_ui(self) -> None:
        self._open_btn.setText(t("progress.open_folder"))
        view = self._progress_view
        self._view_combo.blockSignals(True)
        self._view_combo.clear()
        self._view_combo.addItems([t("progress.view_simple"), t("progress.view_detailed")])
        self._view_combo.setCurrentIndex(1 if view == "detailed" else 0)
        self._view_combo.blockSignals(False)
        if self._title.text() in ("", t("progress.no_video")) or not self._download_items:
            self._title.setText(t("progress.no_video"))
        if self._progress_view == "detailed" and self._download_items:
            self.rebuild_detail_rows()

    def rebuild_detail_rows(self) -> None:
        while self._detailed_layout.count():
            item = self._detailed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._detail_rows = []
        style = self.style()
        for i, item in enumerate(self._download_items):
            row = QHBoxLayout()
            row_w = QWidget()
            row_w.setLayout(row)

            icon_label = QLabel()
            icon_label.setPixmap(_status_icon(style, item["status"]).pixmap(16, 16))
            row.addWidget(icon_label)

            display = item["title"] or truncate_filename(item["url"], 40)
            title_lbl = QLabel(display)
            row.addWidget(title_lbl, stretch=1)

            bar = QProgressBar()
            bar.setMaximum(100)
            bar.setValue(int(item["progress"] * 100))
            bar.setFixedWidth(120)
            row.addWidget(bar)

            info = QLabel(_status_text(item))
            info.setFixedWidth(70)
            row.addWidget(info)

            retry_btn = QPushButton(t("progress.retry"))
            if item["status"] == "failed":
                retry_btn.clicked.connect(lambda _c=False, idx=i: self._on_retry_item(idx))
                row.addWidget(retry_btn)

            self._detailed_layout.addWidget(row_w)
            self._detail_rows.append({
                "icon_label": icon_label,
                "title_label": title_lbl,
                "bar": bar,
                "info_label": info,
                "retry_btn": retry_btn,
                "style": style,
            })

    def update_detail_row(self, index: int) -> None:
        if index >= len(self._detail_rows) or index >= len(self._download_items):
            return
        item = self._download_items[index]
        row = self._detail_rows[index]
        style = row["style"]
        row["icon_label"].setPixmap(_status_icon(style, item["status"]).pixmap(16, 16))
        display = item["title"] or truncate_filename(item["url"], 40)
        row["title_label"].setText(display)
        row["bar"].setValue(int(item["progress"] * 100))
        row["info_label"].setText(_status_text(item))
        if item["status"] == "failed":
            row["retry_btn"].show()
        else:
            row["retry_btn"].hide()


def _status_icon(style: QStyle, status: str) -> QIcon:
    mapping = {
        "queued": QStyle.StandardPixmap.SP_FileDialogListView,
        "downloading": QStyle.StandardPixmap.SP_MediaPlay,
        "done": QStyle.StandardPixmap.SP_DialogApplyButton,
        "failed": QStyle.StandardPixmap.SP_MessageBoxCritical,
    }
    sp = mapping.get(status, QStyle.StandardPixmap.SP_FileDialogListView)
    return style.standardIcon(sp)


def _status_text(item: dict) -> str:
    status = item["status"]
    if status == "queued":
        return t("progress.status_queued")
    if status == "downloading":
        return f"{item['progress'] * 100:.0f}%"
    if status == "done":
        return t("progress.status_done")
    if status == "failed":
        return t("progress.status_failed")
    return ""


class _ViewComboCompat:
    def __init__(self, combo: QComboBox) -> None:
        self._combo = combo

    def grid(self, *args: object, **kwargs: object) -> None:
        pass

    def grid_forget(self) -> None:
        pass
