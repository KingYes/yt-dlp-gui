"""Main application window -- thin coordinator wiring extracted widgets."""

from __future__ import annotations

import contextlib
import os
import queue
import webbrowser
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from .clipboard_dnd import ClipboardDndController
from .download_handler import DownloadHandler
from .download_manager import DownloadManager
from .format_parser import FORMAT_PRESETS
from .i18n import is_rtl, load_language, t
from .layout_utils import _anchor_start, _c, _pad_end, _sticky_end, _sticky_start
from .metadata_pickers import MetadataPickerController
from .queue_controller import QueueController
from .settings_window import SettingsWindow
from .state import AppState
from .updater import APP_VERSION, check_for_update
from .utils import (
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
from .widgets.format_frame import FormatFrame
from .widgets.log_panel import LogPanel
from .widgets.progress_panel import ProgressPanel
from .widgets.queue_panel import QueuePanel
from .widgets.url_frame import UrlFrame


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self._main_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self._drain_scheduled: bool = False

        self.geometry("780x640")
        self.minsize(640, 480)

        ctk.set_default_color_theme("blue")

        self._state = AppState()

        settings = self._state.settings
        load_language(settings.get("language", "en"))
        self.title(t("app.title"))
        ctk.set_appearance_mode(settings.get("theme", "system"))
        ui_scale = settings.get("ui_scale", 1.0)
        if ui_scale != 1.0:
            ctk.set_widget_scaling(ui_scale)

        self._manager = DownloadManager()
        self._dl_handler = DownloadHandler(self, self._manager, self._call_on_main)
        self._queue_ctrl = QueueController(self)
        self._meta_ctrl = MetadataPickerController(self)
        self._clipboard_ctrl = ClipboardDndController(self)
        self._output_dir = str(Path.home() / "Downloads")
        self._video_title: str = ""
        self._accumulated_bytes: int = 0
        self._is_playlist_download: bool = False
        self._is_audio_download: bool = False
        self._current_urls: list[str] = []
        self._history_visible: bool = False
        self._clipboard_last: str = ""
        self._clipboard_job: str | None = None
        self._settings_window: SettingsWindow | None = None

        self._queue: list[dict] = []
        self._input_mode: str = "single"
        self._current_item_index: int = 0
        self._total_items: int = 0

        self._custom_format_enabled: bool = False
        self._available_video_formats: list[dict] = []
        self._available_audio_formats: list[dict] = []

        self._available_subtitles: dict[str, list[dict]] = {"manual": [], "auto": []}
        self._subtitle_vars: dict[str, ctk.BooleanVar] = {}
        self._available_chapters: list[dict] = []
        self._chapter_vars: list[ctk.BooleanVar] = []

        self._subtitle_select_all_var = ctk.BooleanVar(value=False)
        self._subtitle_dialog: ctk.CTkToplevel | None = None
        self._chapter_select_all_var = ctk.BooleanVar(value=True)
        self._chapter_dialog: ctk.CTkToplevel | None = None

        self._build_ui()
        self._restore_state()
        self._restore_geometry()
        self._setup_dnd()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if settings.get("clipboard_monitor"):
            self._start_clipboard_monitor()

        self.after(200, self._startup_checks)

    # -------------------------------------------------- Thread-safe dispatcher

    def _call_on_main(self, func: Callable[[], None]) -> None:
        self._main_queue.put(func)
        if not self._drain_scheduled:
            self._drain_scheduled = True
            try:
                self.after(1, self._drain_main_queue)
            except RuntimeError:
                self._drain_scheduled = False

    def _drain_main_queue(self) -> None:
        self._drain_scheduled = False
        count = 0
        while count < 64:
            try:
                func = self._main_queue.get_nowait()
            except queue.Empty:
                break
            with contextlib.suppress(Exception):
                func()
            count += 1
        if not self._main_queue.empty() and not self._drain_scheduled:
            self._drain_scheduled = True
            self.after(1, self._drain_main_queue)

    # --------------------------------------------------------- Startup checks

    def _startup_checks(self) -> None:
        import threading

        ffmpeg_path = self._state.settings.get("ffmpeg_path", "")

        def _check_ffmpeg_worker() -> None:
            has_ffmpeg = check_ffmpeg(ffmpeg_path)
            if not has_ffmpeg:
                self._call_on_main(self._show_ffmpeg_wizard)
            else:
                self._call_on_main(self._ensure_ffmpeg_in_path)

        threading.Thread(target=_check_ffmpeg_worker, daemon=True).start()

        def _on_update(version: str | None, url: str | None) -> None:
            if version and url:
                self._call_on_main(lambda: self._show_update_banner(version, url))

        check_for_update(_on_update)

    def _show_ffmpeg_wizard(self) -> None:
        from .setup_wizard import SetupWizard

        SetupWizard(self, self._state, on_complete=self._ensure_ffmpeg_in_path)

    def _ensure_ffmpeg_in_path(self) -> None:
        bin_dir = get_bin_dir()
        bin_str = str(bin_dir)
        if bin_dir.exists() and bin_str not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_str + os.pathsep + os.environ.get("PATH", "")

    def _show_update_banner(self, version: str, url: str) -> None:
        banner = ctk.CTkFrame(self._scroll_container, fg_color="#d1ecf1", corner_radius=6)
        banner.grid(row=0, column=0, padx=16, pady=(8, 0), sticky="ew")
        banner.grid_columnconfigure(_c(0, 2), weight=1)

        ctk.CTkLabel(
            banner, text=t("update.banner", version=version),
            font=ctk.CTkFont(size=12), text_color="#0c5460", anchor=_anchor_start(),
        ).grid(row=0, column=_c(0, 2), padx=12, pady=8, sticky=_sticky_start())

        ctk.CTkButton(
            banner, text=t("update.download"), width=80, height=24,
            font=ctk.CTkFont(size=11), command=lambda: webbrowser.open(url),
        ).grid(row=0, column=_c(1, 2), padx=4, pady=8)

        ctk.CTkButton(
            banner, text=t("update.dismiss"), width=60, height=24,
            font=ctk.CTkFont(size=11), command=banner.destroy,
        ).grid(row=0, column=_c(2, 2), padx=_pad_end(8, 0), pady=8)

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll_container.grid(row=0, column=0, sticky="nsew")
        self._scroll_container.grid_columnconfigure(0, weight=1)

        self._url = UrlFrame(
            self._scroll_container,
            on_download=self._on_download,
            on_paste=self._on_paste,
            on_preview=self._on_preview,
            on_settings=self._open_settings,
            on_mode_toggle=self._on_mode_toggle,
            on_url_changed=self._check_url_changed,
        )
        self._url.grid(row=1, column=0, padx=16, pady=(16, 8), sticky="ew")

        self._fmt = FormatFrame(
            self._scroll_container,
            self._state.settings,
            on_download=self._on_download,
            on_cancel=self._on_cancel,
            on_custom_format_toggled=self._on_custom_format_toggled,
            on_section_toggled=self._on_section_toggled,
            on_convert_changed=self._on_convert_changed,
            on_subtitle_mode_changed=self._on_subtitle_mode_changed,
            on_burn_sub_changed=lambda: self._state.save_settings(subtitle_burn=self._fmt.burn_sub_var.get()),
            on_subtitle_edit=self._open_subtitle_picker_dialog,
            on_chapter_edit=self._open_chapter_picker_dialog,
        )
        self._fmt.grid(row=2, column=0, padx=16, pady=4, sticky="ew")

        self._build_output_frame(row=3)

        self._progress = ProgressPanel(
            self._scroll_container,
            on_open_folder=self._on_open_folder,
            on_progress_view_toggle=self._on_progress_view_toggle,
            on_retry_item=self._retry_item,
        )
        self._progress.grid(row=4, column=0, padx=16, pady=4, sticky="ew")

        self._queue_panel = QueuePanel(
            self._scroll_container,
            on_clear=self._clear_queue,
            on_start=self._start_queue,
            on_move=self._move_queue_item,
            on_remove=self._remove_queue_item,
        )
        self._queue_panel.grid(row=5, column=0, padx=16, pady=4, sticky="ew")

        self._log_panel = LogPanel(self._scroll_container, on_toggle_history=self._toggle_history)
        self._log_panel.grid(row=6, column=0, padx=16, pady=(4, 4), sticky="ew")

        self._build_status_bar(row=7)

    def _build_output_frame(self, row: int) -> None:
        frame = ctk.CTkFrame(self._scroll_container)
        frame.grid(row=row, column=0, padx=16, pady=4, sticky="ew")
        frame.grid_columnconfigure(_c(1, 2), weight=1)

        ctk.CTkLabel(frame, text=t("output.label"), font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=_c(0, 2), padx=(12, 6) if not is_rtl() else (6, 12), pady=12
        )

        recent = self._state.recent_folders or [self._output_dir]
        self._folder_var = ctk.StringVar(value=self._output_dir)
        self._folder_menu = ctk.CTkOptionMenu(
            frame, variable=self._folder_var, values=recent,
            command=self._on_folder_selected, dynamic_resizing=False,
        )
        self._folder_menu.grid(row=0, column=_c(1, 2), padx=4, pady=12, sticky="ew")

        ctk.CTkButton(frame, text=t("output.browse"), width=90, command=self._on_browse).grid(
            row=0, column=_c(2, 2), padx=_pad_end(12, 4), pady=12
        )

    def _build_status_bar(self, row: int) -> None:
        bar = ctk.CTkFrame(self._scroll_container, fg_color="transparent")
        bar.grid(row=row, column=0, padx=20, pady=(0, 6), sticky="ew")
        bar.grid_columnconfigure(_c(0, 1), weight=1)

        self._status_bar = ctk.CTkLabel(
            bar, text="", anchor=_anchor_start(), font=ctk.CTkFont(size=11), text_color="gray",
        )
        self._status_bar.grid(row=0, column=_c(0, 1), sticky=_sticky_start())

        ctk.CTkLabel(
            bar, text=f"v{APP_VERSION}", anchor=_sticky_end(),
            font=ctk.CTkFont(size=10), text_color="gray",
        ).grid(row=0, column=_c(1, 1), sticky=_sticky_end())

        self._refresh_status_bar()

    def _refresh_status_bar(self) -> None:
        s = self._state.stats
        videos = s["total_downloads"] - s["total_audio_downloads"]
        audio = s["total_audio_downloads"]
        playlists = s["total_playlist_downloads"]
        transferred = format_bytes(s["total_bytes"])
        self._status_bar.configure(
            text=t("status.bar", videos=videos, audio=audio, playlists=playlists, transferred=transferred)
        )

    # ----------------------------------------------------------- DnD

    def _setup_dnd(self) -> None:
        self._clipboard_ctrl.setup_dnd()

    def _on_dnd_drop(self, event: object) -> None:
        self._clipboard_ctrl._on_dnd_drop(event)

    # ---------------------------------------------------- Download items

    def _init_download_items(self, urls: list[str]) -> None:
        items = [
            {
                "url": u, "status": "queued", "progress": 0.0, "title": "",
                "error": None, "accumulated_bytes": 0,
            }
            for u in urls
        ]
        self._progress.download_items = items
        self._current_item_index = 0
        self._total_items = len(urls)
        if self._input_mode == "multiple":
            self._progress.overall_label.configure(text=t("progress.overall", done=0, total=self._total_items))
        if self._progress.progress_view == "detailed":
            self._progress.rebuild_detail_rows()

    # ---------------------------------------------------- Mode toggle

    def _on_mode_toggle(self, value: str) -> None:
        mode = "multiple" if value == t("url.mode_multiple") else "single"
        if mode == self._input_mode:
            return
        self._switch_mode(mode)

    def _switch_mode(self, mode: str) -> None:
        old_mode = self._input_mode
        self._input_mode = mode
        label = t("url.mode_multiple") if mode == "multiple" else t("url.mode_single")
        self._url.set_mode(label)

        if old_mode == "single":
            text = self._url.url_entry.get().strip()
        else:
            text = self._url.url_textbox.get("1.0", "end").strip()

        if mode == "single":
            self._url.url_textbox.grid_forget()
            self._url.url_entry.grid(row=1, column=0, padx=12, pady=(6, 0), sticky="ew")
            self._url.url_entry.delete(0, "end")
            first_line = text.split("\n")[0].strip() if text else ""
            if first_line:
                self._url.url_entry.insert(0, first_line)
            self._progress.hide_toggle()
        else:
            self._url.url_entry.grid_forget()
            self._url.url_textbox.grid(row=1, column=0, padx=12, pady=(6, 0), sticky="ew")
            self._url.url_textbox.delete("1.0", "end")
            if text:
                self._url.url_textbox.insert("1.0", text)
            self._progress.show_toggle()

        self._update_section_visibility()

    def _auto_switch_to_multiple(self, text: str) -> None:
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        if len(lines) > 1 and self._input_mode == "single":
            self._url.url_entry.delete(0, "end")
            self._switch_mode("multiple")
            self._url.url_textbox.delete("1.0", "end")
            self._url.url_textbox.insert("1.0", "\n".join(lines))

    # ------------------------------------------------- Custom format

    def _on_custom_format_toggled(self) -> None:
        enabled = self._fmt.custom_format_var.get()
        self._custom_format_enabled = enabled
        if enabled:
            self._fmt.custom_format_frame.grid(row=2, column=0, columnspan=4, padx=12, pady=(4, 4), sticky="ew")
            self._fmt.format_menu.configure(state="disabled")
            has_formats = bool(self._available_video_formats or self._available_audio_formats)
            if has_formats:
                self._fmt.video_format_menu.configure(state="normal")
                self._fmt.audio_format_menu.configure(state="normal")
            else:
                self._fmt.format_status_label.configure(text=t("format.load_formats_hint"), text_color="#e0a800")
        else:
            self._fmt.custom_format_frame.grid_forget()
            self._fmt.format_menu.configure(state="normal")

    def _get_custom_format_string(self) -> str:
        return self._meta_ctrl.get_custom_format_string()

    # ------------------------------------------------ Post-processing

    def _on_convert_changed(self, value: str) -> None:
        self._state.save_settings(convert_format="" if value == "None" else value.lower())

    def _on_subtitle_mode_changed(self, value: str) -> None:
        self._state.save_settings(subtitle_mode={"Embed": "embed", "File": "file"}.get(value, ""))

    # ------------------------------------------------- Section

    def _on_section_toggled(self) -> None:
        if self._fmt.section_var.get():
            self._fmt.section_frame.grid(row=1, column=0, columnspan=4, pady=(6, 0), sticky="ew")
            self._fmt.section_error_label.configure(text="")
        else:
            self._fmt.section_frame.grid_forget()
            self._fmt.section_error_label.configure(text="")

    def _update_section_visibility(self) -> None:
        if self._input_mode == "single":
            self._fmt.section_checkbox.grid(row=0, column=_c(1, 3), padx=(0, 8))
            if self._fmt.section_var.get():
                self._fmt.section_frame.grid(row=1, column=0, columnspan=4, pady=(6, 0), sticky="ew")
        else:
            self._fmt.section_checkbox.grid_forget()
            self._fmt.section_frame.grid_forget()
            self._fmt.section_var.set(False)

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

    # ------------------------------------------------- Metadata pickers

    def _check_url_changed(self) -> None:
        current = self._get_urls()
        current_str = "\n".join(current)
        if not hasattr(self, "_last_preview_url_str"):
            self._last_preview_url_str = ""
        if current_str != self._last_preview_url_str and self._last_preview_url_str:
            self._clear_metadata_pickers()

    def _clear_metadata_pickers(self) -> None:
        self._last_preview_url_str = ""
        if self._available_subtitles["manual"] or self._available_subtitles["auto"]:
            self._meta_ctrl.hide_subtitles()
        if self._available_chapters:
            self._meta_ctrl.hide_chapters()

    # ------------------------------------------------- Subtitle picker

    def _open_subtitle_picker_dialog(self) -> None:
        self._meta_ctrl.open_subtitle_dialog()

    def _get_selected_subtitle_langs(self) -> list[str] | None:
        return self._meta_ctrl.get_selected_subtitle_langs()

    # ------------------------------------------------- Chapter picker

    def _open_chapter_picker_dialog(self) -> None:
        self._meta_ctrl.open_chapter_dialog()

    def _get_selected_chapters(self) -> list[str] | None:
        return self._meta_ctrl.get_selected_chapters()

    # --------------------------------------------------- Settings / clipboard

    def _open_settings(self) -> None:
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.focus()
            return
        self._settings_window = SettingsWindow(
            self, self._state,
            on_clipboard_changed=self._on_clipboard_setting_changed,
            on_language_changed=self._on_language_changed,
        )

    def _on_language_changed(self, code: str) -> None:
        load_language(code)
        self.title(t("app.title"))
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
        self._restore_state()
        self._setup_dnd()
        self._refresh_status_bar()

    def _on_clipboard_setting_changed(self, enabled: bool) -> None:
        if enabled:
            self._start_clipboard_monitor()
        else:
            self._stop_clipboard_monitor()

    def _start_clipboard_monitor(self) -> None:
        self._clipboard_ctrl.start_monitor()

    def _stop_clipboard_monitor(self) -> None:
        self._clipboard_ctrl.stop_monitor()

    def _poll_clipboard(self) -> None:
        self._clipboard_ctrl._poll()

    # --------------------------------------------------- History

    def _toggle_history(self) -> None:
        if self._history_visible:
            self._log_panel.show_log()
            self._history_visible = False
        else:
            self._populate_history()
            self._log_panel.show_history()
            self._history_visible = True

    def _populate_history(self) -> None:
        tb = self._log_panel.history_textbox
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        entries = self._state.history
        if not entries:
            tb.insert("1.0", t("history.empty"))
        else:
            for entry in reversed(entries):
                status = t("history.status_ok") if entry.get("status") == "ok" else t("history.status_fail")
                title = entry.get("title", t("history.unknown_title")) or t("history.unknown_title")
                date = entry.get("date", "")[:19].replace("T", " ")
                size = format_bytes(entry.get("bytes", 0))
                url = entry.get("url", "")
                line = f"[{status}] {date} | {truncate_filename(title, 40)} | {size}"
                if url:
                    line += f"\n       {url}"
                tb.insert("end", line + "\n\n")
        tb.configure(state="disabled")

    # --------------------------------------------------- Preview

    def _on_preview(self) -> None:
        urls = self._get_urls()
        if not urls:
            self._url.preview_label.configure(text=t("preview.enter_url"), text_color="gray")
            return
        url = urls[0]
        if not is_valid_url(url):
            self._url.preview_label.configure(text=t("preview.invalid_url"), text_color="#dc3545")
            return
        self._url.preview_label.configure(text=t("preview.fetching"), text_color="gray")
        self._url.preview_btn.configure(state="disabled")

        def _on_info(info: dict | None, error: str | None) -> None:
            self._call_on_main(lambda: self._show_preview(info, error))

        self._manager.extract_info(url, _on_info)

    def _show_preview(self, info: dict | None, error: str | None) -> None:
        self._url.preview_btn.configure(state="normal")
        if error or not info:
            self._url.preview_label.configure(text=t("preview.failed", error=error or "no data"), text_color="#dc3545")
            return
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
        self._url.preview_label.configure(text=" | ".join(parts), text_color="#17a2b8")
        self._last_preview_url_str = "\n".join(self._get_urls())
        self._meta_ctrl.populate_formats(info)
        self._meta_ctrl.populate_subtitles(info)
        self._meta_ctrl.populate_chapters(info)

    # --------------------------------------------------- State

    def _restore_state(self) -> None:
        last = self._state.last_input
        mode = last.get("input_mode", "single")
        if mode not in ("single", "multiple"):
            mode = "single"
        self._switch_mode(mode)

        pview = last.get("progress_view", "simple")
        if pview not in ("simple", "detailed"):
            pview = "simple"
        self._progress.switch_view(pview)

        if last.get("urls"):
            if self._input_mode == "single":
                self._url.url_entry.delete(0, "end")
                self._url.url_entry.insert(0, last["urls"][0] if last["urls"] else "")
            else:
                self._url.url_textbox.delete("1.0", "end")
                self._url.url_textbox.insert("1.0", "\n".join(last["urls"]))

        if last.get("output_dir"):
            self._output_dir = last["output_dir"]
            self._folder_var.set(self._output_dir)
        if last.get("format"):
            fmt = last["format"]
            if fmt in FORMAT_PRESETS:
                self._fmt.format_var.set(fmt)
        if last.get("split_chapters"):
            self._fmt.split_chapters_var.set(True)
        if last.get("download_section"):
            self._fmt.section_var.set(True)
            self._on_section_toggled()
        if last.get("section_start"):
            self._fmt.section_start_entry.delete(0, "end")
            self._fmt.section_start_entry.insert(0, last["section_start"])
        if last.get("section_end"):
            self._fmt.section_end_entry.delete(0, "end")
            self._fmt.section_end_entry.insert(0, last["section_end"])
        if last.get("custom_format_enabled"):
            self._fmt.custom_format_var.set(True)
            self._on_custom_format_toggled()
        self._update_section_visibility()

        recent = self._state.recent_folders
        if recent:
            self._folder_menu.configure(values=recent)
            if self._output_dir not in recent:
                self._folder_var.set(recent[0])
                self._output_dir = recent[0]

        saved_queue = self._state.download_queue
        if saved_queue:
            self._queue = list(saved_queue)
            self._update_queue_label()
            self._queue_panel.rebuild(self._queue)
            self._log(t("log.restored_queue", count=len(self._queue)))

    def _restore_geometry(self) -> None:
        geo = self._state.window_geometry
        if geo:
            with contextlib.suppress(Exception):
                self.geometry(geo)

    # --------------------------------------------------- Close

    def _on_close(self) -> None:
        try:
            self._shutdown()
        except Exception:
            self.destroy()

    def _shutdown(self) -> None:
        self._manager.cancel()
        self._stop_clipboard_monitor()
        with contextlib.suppress(Exception):
            self._state.window_geometry = self.geometry()
        self._persist_queue()
        self._state.flush_pending_save()
        self.destroy()

    # --------------------------------------------------- Actions

    def _get_urls(self) -> list[str]:
        if self._input_mode == "single":
            raw = self._url.url_entry.get().strip()
            return [raw] if raw else []
        raw = self._url.url_textbox.get("1.0", "end").strip()
        if not raw:
            return []
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def _on_paste(self) -> None:
        try:
            text = self.clipboard_get().strip()
            if not text:
                return
            if self._input_mode == "single" and "\n" in text:
                current = self._url.url_entry.get().strip()
                combined = (current + "\n" + text) if current else text
                self._auto_switch_to_multiple(combined)
                return
            if self._input_mode == "single":
                current = self._url.url_entry.get().strip()
                if current:
                    self._auto_switch_to_multiple(current + "\n" + text)
                else:
                    self._url.url_entry.delete(0, "end")
                    self._url.url_entry.insert(0, text)
            else:
                current = self._url.url_textbox.get("1.0", "end").strip()
                if current:
                    self._url.url_textbox.insert("end", "\n" + text)
                else:
                    self._url.url_textbox.delete("1.0", "end")
                    self._url.url_textbox.insert("1.0", text)
        except Exception:
            self._log(t("log.clipboard_error"))

    def _on_browse(self) -> None:
        directory = filedialog.askdirectory(initialdir=self._output_dir)
        if directory:
            self._output_dir = directory
            self._state.add_recent_folder(directory)
            self._folder_var.set(directory)
            self._folder_menu.configure(values=self._state.recent_folders)

    def _on_folder_selected(self, folder: str) -> None:
        self._output_dir = folder

    def _on_open_folder(self) -> None:
        open_folder(self._output_dir)

    def _on_progress_view_toggle(self, value: str) -> None:
        view = "detailed" if value == t("progress.view_detailed") else "simple"
        if view != self._progress.progress_view:
            self._progress.switch_view(view)

    def _update_playlist_hint(self, urls: list[str]) -> None:
        if not urls:
            self._fmt.playlist_label.configure(text="")
            return
        playlist_mode, ambiguous = self._classify_urls(urls)
        if playlist_mode:
            self._fmt.playlist_label.configure(text=t("format.playlist_detected"), text_color="#28a745")
        elif ambiguous:
            self._fmt.playlist_label.configure(text=t("format.playlist_ambiguous"), text_color="#e0a800")
        else:
            self._fmt.playlist_label.configure(text="")

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
            self._update_queue_label()
            self._queue_panel.rebuild(self._queue)
            self._log(t("log.queued_urls", count=len(urls)))
            return
        self._dl_handler.start_download(urls, playlist=playlist_mode)

    def _on_cancel(self) -> None:
        self._manager.cancel()
        self._queue.clear()
        self._persist_queue()
        self._update_queue_label()
        self._queue_panel.rebuild(self._queue)
        self._log(t("log.cancelling"))

    def _retry_item(self, index: int) -> None:
        items = self._progress.download_items
        if index >= len(items):
            return
        item = items[index]
        if item["status"] != "failed":
            return
        if self._manager.is_busy:
            entry = self._build_queue_entry([item["url"]], self._is_playlist_download)
            self._queue.append(entry)
            self._persist_queue()
            self._update_queue_label()
            self._queue_panel.rebuild(self._queue)
            self._log(t("log.queued_retry", url=truncate_filename(item["url"], 50)))
            return
        item["status"] = "queued"
        item["progress"] = 0.0
        item["error"] = None
        if self._progress.progress_view == "detailed":
            self._progress.update_detail_row(index)
        self._dl_handler.retry_single_url(item["url"], index)

    # --------------------------------------------------- Queue

    def _build_queue_entry(self, urls: list[str], playlist: bool) -> dict:
        return self._queue_ctrl.build_entry(urls, playlist)

    def _persist_queue(self) -> None:
        self._queue_ctrl.persist()

    def _update_queue_label(self) -> None:
        self._queue_ctrl.update_label()

    def _clear_queue(self) -> None:
        self._queue_ctrl.clear()

    def _start_queue(self) -> None:
        self._queue_ctrl.start()

    def _move_queue_item(self, index: int, direction: int) -> None:
        self._queue_ctrl.move_item(index, direction)

    def _remove_queue_item(self, index: int) -> None:
        self._queue_ctrl.remove_item(index)

    def _process_queue(self) -> None:
        self._queue_ctrl.process_next()

    def _show_ambiguous_dialog(self, urls: list[str], ambiguous: list[str]) -> None:
        self._queue_ctrl.show_ambiguous_dialog(urls, ambiguous)

    # --------------------------------------------------- Logging

    def _log(self, message: str) -> None:
        self._log_panel.log(message)
