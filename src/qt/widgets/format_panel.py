"""Format selection panel."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...format_parser import FORMAT_PRESETS
from ...i18n import t
from ..compat import BooleanVarCompat, ButtonCompat, EntryCompat, LabelCompat, StringVarCompat


class FormatPanel(QGroupBox):
    """Format / download controls; exposes CTk-like compat attributes for DownloadHandler."""

    def __init__(
        self,
        parent: QWidget | None,
        settings: dict[str, Any],
        *,
        on_download: Callable[[], None],
        on_cancel: Callable[[], None],
        on_custom_format_toggled: Callable[[], None],
        on_section_toggled: Callable[[], None],
        on_convert_changed: Callable[[str], None],
        on_subtitle_mode_changed: Callable[[str], None],
        on_burn_sub_changed: Callable[[], None],
        on_subtitle_edit: Callable[[], None],
        on_chapter_edit: Callable[[], None],
    ) -> None:
        super().__init__(t("format.label"), parent)
        self._custom_format_enabled = False

        root = QVBoxLayout(self)

        row1 = QHBoxLayout()
        self._format_combo = QComboBox()
        self._format_combo.addItems(list(FORMAT_PRESETS.keys()))
        row1.addWidget(self._format_combo, stretch=1)

        self._download_btn = QPushButton(t("format.download"))
        self._download_btn.clicked.connect(on_download)
        row1.addWidget(self._download_btn)

        self._cancel_btn = QPushButton(t("format.cancel"))
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(on_cancel)
        row1.addWidget(self._cancel_btn)
        self.download_btn = ButtonCompat(self._download_btn)
        self.cancel_btn = ButtonCompat(self._cancel_btn)
        root.addLayout(row1)

        self._custom_check = QCheckBox(t("format.custom_format"))
        self._custom_check.toggled.connect(lambda _: on_custom_format_toggled())
        root.addWidget(self._custom_check)

        self.custom_format_frame = QWidget()
        cf_layout = QHBoxLayout(self.custom_format_frame)
        self._cf_video_label = QLabel(t("format.video"))
        cf_layout.addWidget(self._cf_video_label)
        self._video_combo = QComboBox()
        self._video_combo.addItem(t("format.preview_first"))
        self._video_combo.setEnabled(False)
        cf_layout.addWidget(self._video_combo)
        self._cf_audio_label = QLabel(t("format.audio"))
        cf_layout.addWidget(self._cf_audio_label)
        self._audio_combo = QComboBox()
        self._audio_combo.addItem(t("format.preview_first"))
        self._audio_combo.setEnabled(False)
        cf_layout.addWidget(self._audio_combo)
        self._format_status = QLabel("")
        cf_layout.addWidget(self._format_status)
        self.custom_format_frame.hide()
        root.addWidget(self.custom_format_frame)

        opts = QHBoxLayout()
        self._split_check = QCheckBox(t("format.split_chapters"))
        opts.addWidget(self._split_check)

        self.section_checkbox = QCheckBox(t("format.download_section"))
        self.section_checkbox.toggled.connect(lambda _: on_section_toggled())
        opts.addWidget(self.section_checkbox)

        self._queue_label = QLabel("")
        opts.addWidget(self._queue_label)
        self._playlist_label = QLabel("")
        opts.addWidget(self._playlist_label)
        opts.addStretch()
        root.addLayout(opts)

        self.section_frame = QWidget()
        sf = QHBoxLayout(self.section_frame)
        self._section_start_lbl = QLabel(t("format.section_start"))
        sf.addWidget(self._section_start_lbl)
        self._section_start = QLineEdit()
        self._section_start.setPlaceholderText(t("format.section_start_placeholder"))
        self._section_start.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        sf.addWidget(self._section_start)
        self._section_end_lbl = QLabel(t("format.section_end"))
        sf.addWidget(self._section_end_lbl)
        self._section_end = QLineEdit()
        self._section_end.setPlaceholderText(t("format.section_end_placeholder"))
        self._section_end.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        sf.addWidget(self._section_end)
        self._section_error = QLabel("")
        self._section_error.setStyleSheet("color: #dc3545;")
        sf.addWidget(self._section_error)
        self.section_frame.hide()
        root.addWidget(self.section_frame)

        pp = QHBoxLayout()
        self._convert_lbl = QLabel(t("format.convert"))
        pp.addWidget(self._convert_lbl)
        self._convert_combo = QComboBox()
        convert_values = ["None", "MP4", "MKV", "WebM", "MP3", "AAC", "FLAC", "WAV", "OGG"]
        self._convert_combo.addItems(convert_values)
        current_convert = settings.get("convert_format", "")
        convert_display = current_convert.upper() if current_convert else "None"
        if convert_display not in convert_values:
            convert_display = "None"
        self._convert_combo.setCurrentText(convert_display)
        self._convert_combo.currentTextChanged.connect(on_convert_changed)
        pp.addWidget(self._convert_combo)

        self._subs_lbl = QLabel(t("format.subs"))
        pp.addWidget(self._subs_lbl)
        self._sub_combo = QComboBox()
        sub_values = ["None", "Embed", "File"]
        self._sub_combo.addItems(sub_values)
        current_sub = settings.get("subtitle_mode", "")
        sub_display = {"embed": "Embed", "file": "File"}.get(current_sub, "None")
        self._sub_combo.setCurrentText(sub_display)
        self._sub_combo.currentTextChanged.connect(on_subtitle_mode_changed)
        pp.addWidget(self._sub_combo)

        self._burn_check = QCheckBox(t("format.burn_subs"))
        self._burn_check.setChecked(settings.get("subtitle_burn", False))
        self._burn_check.toggled.connect(lambda _: on_burn_sub_changed())
        pp.addWidget(self._burn_check)
        pp.addStretch()
        root.addLayout(pp)

        self.subtitle_summary_frame = QWidget()
        sub_row = QHBoxLayout(self.subtitle_summary_frame)
        self._subtitle_summary = QLabel(t("format.subtitle_none"))
        sub_row.addWidget(self._subtitle_summary, stretch=1)
        self._sub_edit_btn = QPushButton(t("format.edit"))
        self._sub_edit_btn.setFixedWidth(60)
        self._sub_edit_btn.clicked.connect(on_subtitle_edit)
        sub_row.addWidget(self._sub_edit_btn)
        self.subtitle_summary_frame.hide()
        root.addWidget(self.subtitle_summary_frame)

        self.chapter_summary_frame = QWidget()
        ch_row = QHBoxLayout(self.chapter_summary_frame)
        self._chapter_summary = QLabel(t("format.chapters_all"))
        ch_row.addWidget(self._chapter_summary, stretch=1)
        self._ch_edit_btn = QPushButton(t("format.edit"))
        self._ch_edit_btn.setFixedWidth(60)
        self._ch_edit_btn.clicked.connect(on_chapter_edit)
        ch_row.addWidget(self._ch_edit_btn)
        self.chapter_summary_frame.hide()
        root.addWidget(self.chapter_summary_frame)

        # Compat layer for DownloadHandler / CtkDownloadContext-style access via MainWindow._fmt
        self.format_var = StringVarCompat(self.get_format_key, self.set_format_key)
        self.split_chapters_var = BooleanVarCompat(
            lambda: self._split_check.isChecked(),
            self._split_check.setChecked,
        )
        self.section_var = BooleanVarCompat(
            lambda: self.section_checkbox.isChecked(),
            self._on_section_var_set,
        )
        self.convert_var = StringVarCompat(
            lambda: self._convert_combo.currentText(),
            self._convert_combo.setCurrentText,
        )
        self.subtitle_mode_var = StringVarCompat(
            lambda: self._sub_combo.currentText(),
            self._sub_combo.setCurrentText,
        )
        self.burn_sub_var = BooleanVarCompat(
            lambda: self._burn_check.isChecked(),
            self._burn_check.setChecked,
        )
        self.video_format_var = StringVarCompat(
            lambda: self._video_combo.currentText(),
            self._video_combo.setCurrentText,
        )
        self.audio_format_var = StringVarCompat(
            lambda: self._audio_combo.currentText(),
            self._audio_combo.setCurrentText,
        )
        self.section_start_entry = EntryCompat(
            lambda: self._section_start.text(),
            self._section_start.setText,
        )
        self.section_end_entry = EntryCompat(
            lambda: self._section_end.text(),
            self._section_end.setText,
        )
        self.custom_format_var = BooleanVarCompat(
            lambda: self._custom_format_enabled,
            self._set_custom_format_enabled,
        )
        self.format_menu = _ComboCompat(self._format_combo)
        self.video_format_menu = _ComboCompat(self._video_combo)
        self.audio_format_menu = _ComboCompat(self._audio_combo)
        self.playlist_label = LabelCompat(self._playlist_label)
        self.queue_label = LabelCompat(self._queue_label)
        self.section_error_label = LabelCompat(self._section_error)
        self.format_status_label = LabelCompat(self._format_status)
        self.subtitle_summary_label = LabelCompat(self._subtitle_summary)
        self.chapter_summary_label = LabelCompat(self._chapter_summary)

    def show_subtitle_summary(self) -> None:
        self.subtitle_summary_frame.show()

    def hide_subtitle_summary(self) -> None:
        self.subtitle_summary_frame.hide()

    def show_chapter_summary(self) -> None:
        self.chapter_summary_frame.show()

    def hide_chapter_summary(self) -> None:
        self.chapter_summary_frame.hide()

    def _on_section_var_set(self, value: bool) -> None:
        self.section_checkbox.setChecked(value)

    def _set_custom_format_enabled(self, value: bool) -> None:
        self._custom_format_enabled = value
        self._custom_check.setChecked(value)

    def get_format_key(self) -> str:
        return str(self._format_combo.currentText())

    def set_format_key(self, key: str) -> None:
        idx = self._format_combo.findText(key)
        if idx >= 0:
            self._format_combo.setCurrentIndex(idx)

    def set_custom_format_visible(self, visible: bool) -> None:
        self._custom_format_enabled = visible
        if visible:
            self.custom_format_frame.show()
            self._format_combo.setEnabled(False)
        else:
            self.custom_format_frame.hide()
            self._format_combo.setEnabled(True)

    def retranslate_ui(self) -> None:
        self.setTitle(t("format.label"))
        self._download_btn.setText(t("format.download"))
        self._cancel_btn.setText(t("format.cancel"))
        self._custom_check.setText(t("format.custom_format"))
        self._cf_video_label.setText(t("format.video"))
        self._cf_audio_label.setText(t("format.audio"))
        self._split_check.setText(t("format.split_chapters"))
        self.section_checkbox.setText(t("format.download_section"))
        self._section_start_lbl.setText(t("format.section_start"))
        self._section_end_lbl.setText(t("format.section_end"))
        self._section_start.setPlaceholderText(t("format.section_start_placeholder"))
        self._section_end.setPlaceholderText(t("format.section_end_placeholder"))
        self._convert_lbl.setText(t("format.convert"))
        self._subs_lbl.setText(t("format.subs"))
        self._burn_check.setText(t("format.burn_subs"))
        self._sub_edit_btn.setText(t("format.edit"))
        self._ch_edit_btn.setText(t("format.edit"))

    def set_video_audio_formats(self, video_labels: list[str], audio_labels: list[str]) -> None:
        self._video_combo.clear()
        self._audio_combo.clear()
        if video_labels:
            self._video_combo.addItems(video_labels)
            self._video_combo.setEnabled(True)
        else:
            self._video_combo.addItem(t("format.none_available"))
            self._video_combo.setEnabled(False)
        if audio_labels:
            self._audio_combo.addItems(audio_labels)
            self._audio_combo.setEnabled(True)
        else:
            self._audio_combo.addItem(t("format.none_available"))
            self._audio_combo.setEnabled(False)


class _ComboCompat:
    def __init__(self, combo: QComboBox) -> None:
        self._combo = combo

    def configure(self, state: str | None = None, **kwargs: object) -> None:
        if state is not None:
            self._combo.setEnabled(state != "disabled")
