"""Qt main window — download UI coordinator."""

from __future__ import annotations

import os
import re
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..download_handler import DownloadHandler
from ..download_manager import DownloadManager
from ..download_session import DownloadSession
from ..format_parser import FORMAT_PRESETS, build_format_string, normalize_format_preset, parse_formats
from ..i18n import is_rtl, load_language, t
from ..state import AppState
from ..updater import APP_VERSION, check_for_update
from ..utils import (
    check_ffmpeg,
    classify_url,
    format_bytes,
    get_bin_dir,
    is_valid_url,
    open_folder,
    parse_timestamp,
    truncate_filename,
    validate_time_range,
)
from .clipboard import QtClipboardController
from .metadata_pickers import QtMetadataPickerController
from .qt_download_context import QtDownloadContext
from .settings_dialog import SettingsDialog
from .setup_wizard_dialog import SetupWizardDialog
from .tray import TrayController
from .update_banner import UpdateBanner
from .widgets.format_panel import FormatPanel
from .widgets.log_panel import LogPanel
from .widgets.output_panel import OutputPanel
from .widgets.progress_panel import ProgressPanel
from .widgets.queue_panel import QueuePanel
from .widgets.url_panel import UrlPanel

if TYPE_CHECKING:
    pass


class MainWindow(QMainWindow):
    """Qt main window; ``_run_on_main`` marshals worker-thread callbacks to the UI thread."""

    _run_on_main = Signal(object)

    def __init__(self, app_state: AppState) -> None:
        super().__init__()
        self._state = app_state
        settings = self._state.settings
        load_language(settings.get("language", "en"))

        from PySide6.QtWidgets import QApplication

        qapp = QApplication.instance()
        if qapp is not None and isinstance(qapp, QApplication):
            from .theme import apply_theme, apply_ui_scale

            apply_theme(qapp, settings)
            apply_ui_scale(qapp, settings)
            direction = Qt.LayoutDirection.RightToLeft if is_rtl() else Qt.LayoutDirection.LeftToRight
            qapp.setLayoutDirection(direction)

        self.setWindowTitle(t("app.title"))
        self.setMinimumSize(640, 480)
        self.setAcceptDrops(True)
        self._restore_geometry(settings.get("window_geometry", ""))

        self._manager = DownloadManager()
        self._download_ctx = QtDownloadContext(self)
        self._dl_handler = DownloadHandler(self._download_ctx, self._manager, self._schedule_on_main)
        self._clipboard_ctrl = QtClipboardController(self)
        self._metadata = QtMetadataPickerController(self)
        self._settings_dialog: SettingsDialog | None = None
        self._history_visible = False
        self._update_banner: UpdateBanner | None = None
        self._content_layout: QVBoxLayout | None = None

        self._output_dir = str(Path.home() / "Downloads")
        self._download_session = DownloadSession()
        self._queue: list[dict] = []
        self._input_mode = "single"
        self._custom_format_enabled = False
        self._available_video_formats: list[dict] = []
        self._available_audio_formats: list[dict] = []
        self._last_preview_url_str = ""

        self._run_on_main.connect(self._exec_on_main)

        self._build_ui()
        self._build_menu()
        self._tray = TrayController(self)
        self._restore_state()

        if settings.get("clipboard_monitor"):
            self._clipboard_ctrl.start()

        QTimer.singleShot(200, self._startup_checks)

    def _exec_on_main(self, func: object) -> None:
        if callable(func):
            func()

    def _schedule_on_main(self, func: Callable[[], None]) -> None:
        """Thread-safe: emit from worker threads; Qt delivers on the main thread."""
        self._run_on_main.emit(func)

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._container = QWidget()
        container = self._container
        layout = QVBoxLayout(container)
        self._content_layout = layout

        self._url_panel = UrlPanel(
            container,
            on_download=self._on_download,
            on_paste=self._on_paste,
            on_preview=self._on_preview,
            on_settings=self._open_settings,
            on_mode_changed=self._on_mode_changed,
            on_url_changed=self._check_url_changed,
        )
        layout.addWidget(self._url_panel)

        self._fmt = FormatPanel(
            container,
            self._state.settings,
            on_download=self._on_download,
            on_cancel=self._on_cancel,
            on_custom_format_toggled=self._on_custom_format_toggled,
            on_section_toggled=self._on_section_toggled,
            on_convert_changed=self._on_convert_changed,
            on_subtitle_mode_changed=self._on_subtitle_mode_changed,
            on_burn_sub_changed=lambda: self._state.save_settings(subtitle_burn=self._fmt.burn_sub_var.get()),
            on_subtitle_edit=self._metadata.open_subtitle_dialog,
            on_chapter_edit=self._metadata.open_chapter_dialog,
        )
        layout.addWidget(self._fmt)

        self._queue_panel = QueuePanel(
            container,
            on_clear=self._clear_queue,
            on_start=self._start_queue,
            on_move=self._move_queue_item,
            on_remove=self._remove_queue_item,
        )
        layout.addWidget(self._queue_panel)

        self._output_panel = OutputPanel(
            container,
            on_browse=self._on_browse,
            on_folder_selected=self._on_folder_selected,
        )
        layout.addWidget(self._output_panel)
        self._folder_menu = self._output_panel._folder_menu

        self._progress = ProgressPanel(
            container,
            on_open_folder=self._on_open_folder,
            on_view_changed=self._on_progress_view_toggle,
            on_retry_item=self._retry_item,
        )
        layout.addWidget(self._progress)

        self._log_panel = LogPanel(container, on_toggle_history=self._toggle_history)
        layout.addWidget(self._log_panel)

        layout.addStretch()
        scroll.setWidget(container)
        self.setCentralWidget(scroll)

        status = self.statusBar()
        self._status_label = QLabel("")
        status.addWidget(self._status_label, stretch=1)
        self._version_label = QLabel(f"v{APP_VERSION}")
        status.addPermanentWidget(self._version_label)
        self._refresh_status_bar()

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        for action in list(menubar.actions()):
            menubar.removeAction(action)

        self._file_menu = menubar.addMenu(t("menu.file"))
        self._exit_action = QAction(t("menu.exit"), self)
        self._exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self._exit_action.triggered.connect(self.close)
        self._file_menu.addAction(self._exit_action)

        self._edit_menu = menubar.addMenu(t("menu.edit"))
        self._undo_action = QAction(t("menu.undo"), self)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.triggered.connect(self._edit_undo)
        self._edit_menu.addAction(self._undo_action)

        self._redo_action = QAction(t("menu.redo"), self)
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.triggered.connect(self._edit_redo)
        self._edit_menu.addAction(self._redo_action)

        self._help_menu = menubar.addMenu(t("menu.help"))
        self._about_action = QAction(t("menu.about"), self)
        self._about_action.triggered.connect(self._show_about)
        self._help_menu.addAction(self._about_action)

    def _edit_undo(self) -> None:
        widget = self._url_panel.focus_text_widget()
        if hasattr(widget, "undo"):
            widget.undo()

    def _edit_redo(self) -> None:
        widget = self._url_panel.focus_text_widget()
        if hasattr(widget, "redo"):
            widget.redo()

    def _restore_geometry(self, geometry: str) -> None:
        if not geometry or "x" not in geometry.lower():
            self.resize(780, 640)
            return
        match = re.match(r"^(\d+)x(\d+)(?:\+(-?\d+)\+(-?\d+))?$", geometry.strip())
        if not match:
            self.resize(780, 640)
            return
        w, h = int(match.group(1)), int(match.group(2))
        self.resize(max(w, 640), max(h, 480))
        if match.group(3) is not None and match.group(4) is not None:
            self.move(int(match.group(3)), int(match.group(4)))

    def _startup_checks(self) -> None:
        if not self._check_ytdlp_available():
            return

        ffmpeg_path = self._state.settings.get("ffmpeg_path", "")

        def _worker() -> None:
            has_ffmpeg = check_ffmpeg(ffmpeg_path)
            if not has_ffmpeg:
                self._schedule_on_main(self._show_ffmpeg_wizard)
            else:
                self._schedule_on_main(self._ensure_ffmpeg_in_path)

        threading.Thread(target=_worker, daemon=True).start()

        def _on_update(version: str | None, url: str | None) -> None:
            if version and url:
                self._schedule_on_main(lambda: self._show_update_banner(version, url))

        check_for_update(_on_update)

    def _check_ytdlp_available(self) -> bool:
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            QMessageBox.critical(
                self,
                t("app.title"),
                t("qt.ytdlp_missing"),
            )
            self._log(t("qt.ytdlp_missing"))
            return False
        return True

    def _show_ffmpeg_wizard(self) -> None:
        dialog = SetupWizardDialog(
            self,
            self._state,
            on_complete=self._ensure_ffmpeg_in_path,
            schedule_on_main=self._schedule_on_main,
        )
        dialog.exec()

    def _show_ffmpeg_warning(self) -> None:
        QMessageBox.warning(self, t("app.title"), t("qt.ffmpeg_missing"))

    def _ensure_ffmpeg_in_path(self) -> None:
        bin_dir = get_bin_dir()
        bin_str = str(bin_dir)
        if bin_dir.exists() and bin_str not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_str + os.pathsep + os.environ.get("PATH", "")

    def _show_update_banner(self, version: str, url: str) -> None:
        self._log(t("update.banner", version=version))
        if self._update_banner is not None or self._content_layout is None:
            return

        def _dismiss() -> None:
            if self._update_banner is not None:
                self._update_banner.deleteLater()
                self._update_banner = None

        self._update_banner = UpdateBanner(
            self._container,
            t("update.banner", version=version),
            url,
            on_dismiss=_dismiss,
            download_label=t("update.download"),
            dismiss_label=t("update.dismiss"),
        )
        self._content_layout.insertWidget(0, self._update_banner)

    def _show_about(self) -> None:
        QMessageBox.about(self, t("app.title"), t("qt.about_text", version=APP_VERSION))

    def _refresh_status_bar(self) -> None:
        s = self._state.stats
        videos = s["total_downloads"] - s["total_audio_downloads"]
        audio = s["total_audio_downloads"]
        playlists = s["total_playlist_downloads"]
        transferred = format_bytes(s["total_bytes"])
        self._status_label.setText(
            t("status.bar", videos=videos, audio=audio, playlists=playlists, transferred=transferred)
        )

    def _log(self, message: str) -> None:
        self._log_panel.log(message)

    def _get_urls(self) -> list[str]:
        return self._url_panel.get_urls()

    def _on_mode_changed(self, mode: str) -> None:
        self._input_mode = mode
        if mode == "multiple":
            self._progress.show_toggle()
        else:
            self._progress.hide_toggle()
        self._update_section_visibility()

    def _update_section_visibility(self) -> None:
        if self._input_mode == "single":
            self._fmt.section_checkbox.show()
            if self._fmt.section_var.get():
                self._fmt.section_frame.show()
            else:
                self._fmt.section_frame.hide()
        else:
            self._fmt.section_checkbox.hide()
            self._fmt.section_frame.hide()
            self._fmt.section_var.set(False)

    def _on_section_toggled(self) -> None:
        if self._fmt.section_var.get():
            self._fmt.section_frame.show()
            self._fmt.section_error_label.configure(text="")
        else:
            self._fmt.section_frame.hide()

    def _on_custom_format_toggled(self) -> None:
        enabled = self._fmt.custom_format_var.get()
        self._custom_format_enabled = enabled
        self._fmt.set_custom_format_visible(enabled)
        if enabled and not (self._available_video_formats or self._available_audio_formats):
            self._fmt.format_status_label.configure(text=t("format.load_formats_hint"))

    def _get_custom_format_string(self) -> str:
        if not self._custom_format_enabled:
            return ""
        video_label = self._fmt.video_format_var.get()
        audio_label = self._fmt.audio_format_var.get()
        video_id = ""
        audio_id = ""
        for f in self._available_video_formats:
            if f["label"] == video_label:
                video_id = f["format_id"]
                break
        for f in self._available_audio_formats:
            if f["label"] == audio_label:
                audio_id = f["format_id"]
                break
        return build_format_string(video_id, audio_id)

    def _get_selected_chapters(self) -> list[str] | None:
        return self._metadata.get_selected_chapters()

    def _get_selected_subtitle_langs(self) -> list[str] | None:
        return self._metadata.get_selected_subtitle_langs()

    def _validate_section(self) -> bool:
        if not self._fmt.section_var.get():
            return True
        start = self._fmt.section_start_entry.get().strip()
        end = self._fmt.section_end_entry.get().strip()
        if not start and not end:
            self._fmt.section_error_label.configure(text=t("section.error_enter_time"))
            return False
        if start and parse_timestamp(start) is None:
            self._fmt.section_error_label.configure(text=t("section.error_invalid_start"))
            return False
        if end and parse_timestamp(end) is None:
            self._fmt.section_error_label.configure(text=t("section.error_invalid_end"))
            return False
        err = validate_time_range(start, end)
        if err:
            self._fmt.section_error_label.configure(text=err)
            return False
        self._fmt.section_error_label.configure(text="")
        return True

    def _classify_urls(self, urls: list[str]) -> tuple[bool, list[str]]:
        ambiguous: list[str] = []
        playlist_mode = False
        for u in urls:
            kind = classify_url(u)
            if kind == "playlist":
                playlist_mode = True
            elif kind == "ambiguous":
                ambiguous.append(u)
        return playlist_mode, ambiguous

    def _update_playlist_hint(self, urls: list[str]) -> None:
        if not urls:
            self._fmt.playlist_label.configure(text="")
            return
        playlist_mode, ambiguous = self._classify_urls(urls)
        if playlist_mode:
            self._fmt.playlist_label.configure(text=t("format.playlist_detected"))
        elif ambiguous:
            self._fmt.playlist_label.configure(text=t("format.playlist_ambiguous"))
        else:
            self._fmt.playlist_label.configure(text="")

    def _on_download(self) -> None:
        urls = self._get_urls()
        if not urls:
            self._log(t("log.enter_url"))
            return
        invalid = [u for u in urls if not is_valid_url(u)]
        if invalid:
            self._log(t("log.invalid_urls", urls=", ".join(invalid)))
            return
        if not self._validate_section():
            return
        playlist_mode, ambiguous = self._classify_urls(urls)
        self._update_playlist_hint(urls)
        if ambiguous and not playlist_mode:
            self._show_ambiguous_dialog(urls, ambiguous)
            return
        if self._manager.is_busy:
            entry = self._build_queue_entry(urls, playlist_mode)
            self._queue.append(entry)
            self._persist_queue()
            self._update_queue_ui()
            self._log(t("log.queued_urls", count=len(urls)))
            self._log(t("log.queued_format", format=entry["format_key"]))
            return
        self._dl_handler.start_download(urls, playlist=playlist_mode)

    def _show_ambiguous_dialog(self, urls: list[str], ambiguous: list[str]) -> None:
        msg = t("dialog.playlist_single_url") if len(ambiguous) == 1 else t("dialog.playlist_multi_url", count=len(ambiguous))
        box = QMessageBox(self)
        box.setWindowTitle(t("dialog.playlist_title"))
        box.setText(msg)
        box.setIcon(QMessageBox.Icon.Question)
        yes_btn = box.addButton(t("dialog.entire_playlist"), QMessageBox.ButtonRole.YesRole)
        box.addButton(t("dialog.single_video_only"), QMessageBox.ButtonRole.NoRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is None or box.standardButton(clicked) == QMessageBox.StandardButton.Cancel:
            return
        playlist_mode = clicked == yes_btn
        if self._manager.is_busy:
            self._queue.append(self._build_queue_entry(urls, playlist_mode))
            self._persist_queue()
            self._update_queue_ui()
            self._log(t("log.queued_urls", count=len(urls)))
            return
        self._dl_handler.start_download(urls, playlist=playlist_mode)

    def _build_queue_entry(self, urls: list[str], playlist: bool) -> dict:
        form = self._download_ctx.get_form_state()
        return {
            "urls": urls,
            "playlist": playlist,
            "format_key": form.format_key,
            "output_dir": form.output_dir,
            "split_chapters": form.split_chapters,
            "custom_format_string": form.custom_format_string if form.custom_format_enabled else "",
            "section_start": form.section_start,
            "section_end": form.section_end,
            "convert_format": "" if form.convert_format == "None" else form.convert_format.lower(),
            "subtitle_mode": {"Embed": "embed", "File": "file"}.get(form.subtitle_mode, ""),
            "subtitle_burn": form.subtitle_burn,
            "selected_chapters": self._get_selected_chapters(),
            "selected_subtitle_langs": self._get_selected_subtitle_langs(),
            "status": "queued",
        }

    def _on_cancel(self) -> None:
        self._manager.cancel()
        self._queue.clear()
        self._persist_queue()
        self._update_queue_ui()
        self._log(t("log.cancelling"))

    def _on_paste(self) -> None:
        from PySide6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        text = clipboard.text().strip() if clipboard else ""
        if text:
            self._url_panel.append_text(text)

    def _on_preview(self) -> None:
        if not self._check_ytdlp_available():
            self._url_panel.set_preview_text(t("qt.ytdlp_missing_short"), "#dc3545")
            return
        urls = self._get_urls()
        if not urls:
            self._url_panel.set_preview_text(t("preview.enter_url"), "gray")
            return
        url = urls[0]
        if not is_valid_url(url):
            self._url_panel.set_preview_text(t("preview.invalid_url"), "#dc3545")
            return
        self._url_panel.set_preview_text(t("preview.fetching"), "gray")
        self._url_panel.set_preview_enabled(False)

        def _on_info(info: dict | None, error: str | None) -> None:
            self._schedule_on_main(lambda: self._show_preview(info, error))

        self._manager.extract_info(url, _on_info)

    def _show_preview(self, info: dict | None, error: str | None) -> None:
        self._url_panel.set_preview_enabled(True)
        if error or not info:
            self._url_panel.set_preview_text(t("preview.failed", error=error or "no data"), "#dc3545")
            return
        try:
            self._apply_preview_info(info)
        except Exception as exc:
            self._url_panel.set_preview_text(t("preview.failed", error=str(exc)), "#dc3545")

    def _apply_preview_info(self, info: dict) -> None:
        title = info.get("title", t("history.unknown_title"))
        duration = info.get("duration")
        uploader = info.get("uploader", "")
        dur_str = ""
        if duration:
            m, s = divmod(int(duration), 60)
            h, m = divmod(m, 60)
            dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        parts = [title]
        if uploader:
            parts.append(t("preview.by_uploader", uploader=uploader))
        if dur_str:
            parts.append(f"[{dur_str}]")
        entries = info.get("entries")
        if entries:
            parts.append(t("preview.items_count", count=len(entries)))
        self._url_panel.set_preview_text(" | ".join(parts), "#17a2b8")
        self._last_preview_url_str = "\n".join(self._get_urls())
        self._populate_formats(info)
        self._metadata.populate_subtitles(info)
        self._metadata.populate_chapters(info)

    def _populate_formats(self, info: dict) -> None:
        video_formats, audio_formats = parse_formats(info)
        self._available_video_formats = video_formats
        self._available_audio_formats = audio_formats
        video_labels = [f["label"] for f in self._available_video_formats]
        audio_labels = [f["label"] for f in self._available_audio_formats]
        self._fmt.set_video_audio_formats(video_labels, audio_labels)
        if self._custom_format_enabled:
            count = t("format.count", video=len(video_labels), audio=len(audio_labels))
            self._fmt.format_status_label.configure(text=count)

    def _on_browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, t("output.browse"), self._output_dir)
        if directory:
            self._output_dir = directory
            self._state.add_recent_folder(directory)
            self._output_panel.set_folders(self._state.recent_folders, directory)

    def _on_folder_selected(self, folder: str) -> None:
        self._output_dir = folder

    def _on_open_folder(self) -> None:
        open_folder(self._output_dir)

    def _on_progress_view_toggle(self, view: str) -> None:
        if view != self._progress.progress_view:
            self._progress.switch_view(view)

    def _init_download_items(self, urls: list[str]) -> None:
        items = [
            {"url": u, "status": "queued", "progress": 0.0, "title": "", "error": None, "accumulated_bytes": 0}
            for u in urls
        ]
        self._progress.download_items = items
        session = self._download_session
        session.current_item_index = 0
        session.total_items = len(urls)
        session.input_mode = self._input_mode
        if self._input_mode == "multiple":
            self._progress.overall_label.configure(text=t("progress.overall", done=0, total=session.total_items))
        if self._progress.progress_view == "detailed":
            self._progress.rebuild_detail_rows()

    def _retry_item(self, index: int) -> None:
        items = self._progress.download_items
        if index >= len(items):
            return
        item = items[index]
        if item["status"] != "failed":
            return
        if self._manager.is_busy:
            self._queue.append(self._build_queue_entry([item["url"]], self._download_session.is_playlist_download))
            self._persist_queue()
            self._update_queue_ui()
            self._log(t("log.queued_retry", url=truncate_filename(item["url"], 50)))
            return
        item["status"] = "queued"
        item["progress"] = 0.0
        item["error"] = None
        if self._progress.progress_view == "detailed":
            self._progress.update_detail_row(index)
        self._dl_handler.retry_single_url(item["url"], index)

    def _check_url_changed(self) -> None:
        current = self._get_urls()
        current_str = "\n".join(current)
        if current_str != self._last_preview_url_str and self._last_preview_url_str:
            self._available_video_formats = []
            self._available_audio_formats = []
            self._metadata.hide_subtitles()
            self._metadata.hide_chapters()

    def _on_convert_changed(self, value: str) -> None:
        self._state.save_settings(convert_format="" if value == "None" else value.lower())

    def _on_subtitle_mode_changed(self, value: str) -> None:
        self._state.save_settings(subtitle_mode={"Embed": "embed", "File": "file"}.get(value, ""))

    def _open_settings(self) -> None:
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        self._settings_dialog = SettingsDialog(
            self,
            self._state,
            on_theme_changed=self._on_theme_changed,
            on_clipboard_changed=self._on_clipboard_setting_changed,
            on_language_changed=self._on_language_changed,
        )
        self._settings_dialog.finished.connect(lambda: setattr(self, "_settings_dialog", None))
        self._settings_dialog.show()

    def _on_theme_changed(self) -> None:
        from PySide6.QtWidgets import QApplication

        from .theme import apply_theme, apply_ui_scale

        app = QApplication.instance()
        if app is not None and isinstance(app, QApplication):
            apply_theme(app, self._state.settings)
            apply_ui_scale(app, self._state.settings)
            self.update()

    def _on_clipboard_setting_changed(self, enabled: bool) -> None:
        if enabled:
            self._clipboard_ctrl.start()
        else:
            self._clipboard_ctrl.stop()

    def _on_language_changed(self, code: str) -> None:
        from ..i18n import is_rtl, load_language

        load_language(code)
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if isinstance(app, QApplication):
            direction = Qt.LayoutDirection.RightToLeft if is_rtl() else Qt.LayoutDirection.LeftToRight
            app.setLayoutDirection(direction)
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(t("app.title"))
        self._build_menu()
        self._url_panel.retranslate_ui()
        self._fmt.retranslate_ui()
        self._output_panel.retranslate_ui()
        self._progress.retranslate_ui()
        self._queue_panel.retranslate_ui(len(self._queue))
        if self._queue:
            self._queue_panel.rebuild(self._queue)
        self._log_panel.retranslate_ui()
        if self._history_visible:
            self._populate_history()
        self._tray.retranslate_ui()
        self._refresh_status_bar()
        self._update_queue_label()

    def _toggle_history(self) -> None:
        if self._history_visible:
            self._log_panel.show_log()
            self._history_visible = False
        else:
            self._populate_history()
            self._log_panel.show_history()
            self._history_visible = True

    def _populate_history(self) -> None:
        entries = self._state.history
        if not entries:
            self._log_panel.set_history_text(t("history.empty"))
            return
        lines: list[str] = []
        for entry in reversed(entries):
            status = t("history.status_ok") if entry.get("status") == "ok" else t("history.status_fail")
            title = entry.get("title", t("history.unknown_title")) or t("history.unknown_title")
            date = entry.get("date", "")[:19].replace("T", " ")
            size = format_bytes(entry.get("bytes", 0))
            url = entry.get("url", "")
            line = f"[{status}] {date} | {truncate_filename(title, 40)} | {size}"
            if url:
                line += f"\n       {url}"
            lines.append(line)
        self._log_panel.set_history_text("\n\n".join(lines))

    def quit_application(self) -> None:
        self._shutdown()
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _shutdown(self) -> None:
        self._manager.cancel()
        self._clipboard_ctrl.stop()
        self._tray.quit()
        size = self.size()
        pos = self.pos()
        geometry = f"{size.width()}x{size.height()}+{pos.x()}+{pos.y()}"
        self._state._data["window_geometry"] = geometry
        self._persist_queue()
        self._state.flush_pending_save()

    def _update_queue_label(self) -> None:
        count = len(self._queue)
        self._fmt.queue_label.configure(text=t("queue.label_count", count=count) if count else "")

    def _update_queue_ui(self) -> None:
        self._update_queue_label()
        self._queue_panel.rebuild(self._queue)

    def _clear_queue(self) -> None:
        self._queue.clear()
        self._persist_queue()
        self._update_queue_ui()
        self._log(t("log.queue_cleared"))

    def _start_queue(self) -> None:
        if not self._queue:
            return
        if self._manager.is_busy:
            self._log(t("log.already_downloading"))
            return
        self._process_queue()

    def _move_queue_item(self, index: int, direction: int) -> None:
        new_index = index + direction
        if new_index < 0 or new_index >= len(self._queue):
            return
        self._queue[index], self._queue[new_index] = self._queue[new_index], self._queue[index]
        self._persist_queue()
        self._update_queue_ui()

    def _remove_queue_item(self, index: int) -> None:
        if 0 <= index < len(self._queue):
            removed = self._queue.pop(index)
            urls = removed.get("urls", [])
            self._persist_queue()
            self._update_queue_ui()
            self._log(t("log.removed_from_queue", url=truncate_filename(urls[0], 40) if urls else "?"))

    def _restore_state(self) -> None:
        last = self._state.last_input
        mode = last.get("input_mode", "single")
        if mode not in ("single", "multiple"):
            mode = "single"
        self._url_panel.set_mode(mode)
        self._on_mode_changed(mode)

        pview = last.get("progress_view", "simple")
        if pview not in ("simple", "detailed"):
            pview = "simple"
        self._progress.switch_view(pview)

        if last.get("urls"):
            self._url_panel.set_urls(last["urls"])

        if last.get("output_dir"):
            self._output_dir = last["output_dir"]
        recent = self._state.recent_folders or [self._output_dir]
        self._output_panel.set_folders(recent, self._output_dir)

        if last.get("format"):
            fmt = normalize_format_preset(last["format"])
            if fmt in FORMAT_PRESETS:
                self._fmt.set_format_key(fmt)
        if last.get("split_chapters"):
            self._fmt.split_chapters_var.set(True)
        if last.get("download_section"):
            self._fmt.section_var.set(True)
            self._on_section_toggled()
        if last.get("section_start"):
            self._fmt.section_start_entry.insert(0, last["section_start"])
        if last.get("section_end"):
            self._fmt.section_end_entry.insert(0, last["section_end"])
        if last.get("custom_format_enabled"):
            self._fmt.custom_format_var.set(True)
            self._on_custom_format_toggled()
        self._update_section_visibility()

        saved_queue = self._state.download_queue
        if saved_queue:
            self._queue = list(saved_queue)
            self._update_queue_ui()
            self._log(t("log.restored_queue", count=len(self._queue)))

    def _persist_queue(self) -> None:
        self._state._data["download_queue"] = list(self._queue)
        self._state.save_debounced()

    def _process_queue(self) -> None:
        if self._manager.is_busy or not self._queue:
            return
        entry = self._queue.pop(0)
        self._persist_queue()
        self._update_queue_ui()
        self._dl_handler.start_download_from_entry(entry)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        text = event.mimeData().text().strip()
        if text:
            if self._input_mode == "single" and "\n" in text:
                self._url_panel.set_mode("multiple")
                self._on_mode_changed("multiple")
            self._url_panel.append_text(text)
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._tray.handle_close_event():
            event.ignore()
            return
        self._shutdown()
        super().closeEvent(event)
