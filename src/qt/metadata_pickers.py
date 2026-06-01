"""Subtitle and chapter picker state for the Qt main window."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QCheckBox

from ..download_manager import parse_chapters, parse_subtitles
from ..i18n import t
from .widgets.chapter_picker_dialog import ChapterPickerDialog
from .widgets.subtitle_picker_dialog import SubtitlePickerDialog

if TYPE_CHECKING:
    from .main_window import MainWindow


class QtMetadataPickerController:
    def __init__(self, window: MainWindow) -> None:
        self._win = window
        self._available_subtitles: dict[str, list[dict]] = {"manual": [], "auto": []}
        self._subtitle_checks: dict[str, QCheckBox] = {}
        self._subtitle_dialog: SubtitlePickerDialog | None = None

        self._available_chapters: list[dict] = []
        self._chapter_checks: list[QCheckBox] = []
        self._chapter_dialog: ChapterPickerDialog | None = None

    def populate_subtitles(self, info: dict) -> None:
        win = self._win
        subs = parse_subtitles(info)
        self._available_subtitles = subs
        self._subtitle_checks.clear()
        if not (subs["manual"] or subs["auto"]):
            win._fmt.hide_subtitle_summary()
            return
        for entry in subs["manual"]:
            code = entry["code"]
            self._subtitle_checks[code] = QCheckBox()
            self._subtitle_checks[code].setChecked(False)
        for entry in subs["auto"]:
            key = f"auto:{entry['code']}"
            self._subtitle_checks[key] = QCheckBox()
            self._subtitle_checks[key].setChecked(False)
        self.update_subtitle_summary()
        win._fmt.show_subtitle_summary()

    def hide_subtitles(self) -> None:
        self._available_subtitles = {"manual": [], "auto": []}
        self._subtitle_checks.clear()
        if self._subtitle_dialog is not None:
            self._subtitle_dialog.close()
            self._subtitle_dialog = None
        self._win._fmt.hide_subtitle_summary()

    def update_subtitle_summary(self) -> None:
        total = len(self._subtitle_checks)
        selected = sum(1 for cb in self._subtitle_checks.values() if cb.isChecked())
        if selected == 0:
            text = t("format.subtitle_summary_none", total=total)
        elif selected == total:
            text = t("format.subtitle_summary_all", total=total)
        else:
            text = t("format.subtitle_summary_some", selected=selected, total=total)
        self._win._fmt.subtitle_summary_label.configure(text=text)

    def open_subtitle_dialog(self) -> None:
        win = self._win
        if self._subtitle_dialog is not None and self._subtitle_dialog.isVisible():
            self._subtitle_dialog.raise_()
            self._subtitle_dialog.activateWindow()
            return
        self._subtitle_dialog = SubtitlePickerDialog(
            win,
            self._available_subtitles,
            self._subtitle_checks,
            on_close=self.update_subtitle_summary,
        )
        self._subtitle_dialog.show()

    def get_selected_subtitle_langs(self) -> list[str] | None:
        if not self._subtitle_checks:
            return None
        selected: list[str] = []
        for key, cb in self._subtitle_checks.items():
            if cb.isChecked():
                code = key.replace("auto:", "")
                if code not in selected:
                    selected.append(code)
        return selected if selected else None

    def populate_chapters(self, info: dict) -> None:
        win = self._win
        chapters = parse_chapters(info)
        self._available_chapters = chapters
        self._chapter_checks.clear()
        if not chapters:
            win._fmt.hide_chapter_summary()
            return
        for _ch in chapters:
            cb = QCheckBox()
            cb.setChecked(True)
            self._chapter_checks.append(cb)
        self.update_chapter_summary()
        win._fmt.show_chapter_summary()

    def hide_chapters(self) -> None:
        self._available_chapters = []
        self._chapter_checks.clear()
        if self._chapter_dialog is not None:
            self._chapter_dialog.close()
            self._chapter_dialog = None
        self._win._fmt.hide_chapter_summary()

    def update_chapter_summary(self) -> None:
        total = len(self._chapter_checks)
        selected = sum(1 for cb in self._chapter_checks if cb.isChecked())
        if selected == total:
            text = t("format.chapter_summary_all", total=total)
        elif selected == 0:
            text = t("format.chapter_summary_none", total=total)
        else:
            text = t("format.chapter_summary_some", selected=selected, total=total)
        self._win._fmt.chapter_summary_label.configure(text=text)

    def open_chapter_dialog(self) -> None:
        win = self._win
        if self._chapter_dialog is not None and self._chapter_dialog.isVisible():
            self._chapter_dialog.raise_()
            self._chapter_dialog.activateWindow()
            return
        self._chapter_dialog = ChapterPickerDialog(
            win,
            self._available_chapters,
            self._chapter_checks,
            on_close=self.update_chapter_summary,
        )
        self._chapter_dialog.show()

    def get_selected_chapters(self) -> list[str] | None:
        if not self._chapter_checks or not self._available_chapters:
            return None
        selected: list[str] = []
        all_selected = True
        for i, cb in enumerate(self._chapter_checks):
            if cb.isChecked():
                selected.append(self._available_chapters[i]["title"])
            else:
                all_selected = False
        if all_selected:
            return None
        return selected if selected else None
