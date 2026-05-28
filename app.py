import contextlib
import os
import queue
import webbrowser
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from download_manager import (
    FORMAT_PRESETS,
    DownloadManager,
    build_format_string,
    parse_chapters,
    parse_formats,
    parse_subtitles,
)
from i18n import is_rtl, load_language, t
from settings_window import SettingsWindow
from setup_wizard import SetupWizard
from state import AppState
from tray import TrayManager
from updater import APP_VERSION, check_for_update
from utils import (
    check_ffmpeg,
    classify_url,
    format_bytes,
    format_chapter_range,
    format_eta,
    format_speed,
    get_bin_dir,
    is_valid_url,
    open_folder,
    parse_timestamp,
    send_notification,
    truncate_filename,
    validate_time_range,
)

try:
    from tkinterdnd2 import DND_TEXT  # type: ignore[import-untyped]

    _HAS_DND = True
except ImportError:
    _HAS_DND = False


def _anchor_start() -> str:
    """Return 'e' for RTL languages, 'w' for LTR."""
    return "e" if is_rtl() else "w"


def _sticky_start() -> str:
    """Return 'e' for RTL languages, 'w' for LTR."""
    return "e" if is_rtl() else "w"


def _sticky_end() -> str:
    """Return 'w' for RTL languages, 'e' for LTR."""
    return "w" if is_rtl() else "e"


def _pad_start(outer: int = 0, inner: int = 0) -> tuple[int, int]:
    """Return (left, right) padding — `outer` on the start side, `inner` on end."""
    return (inner, outer) if is_rtl() else (outer, inner)


def _pad_end(outer: int = 0, inner: int = 0) -> tuple[int, int]:
    """Return (left, right) padding — `outer` on the end side, `inner` on start."""
    return (outer, inner) if is_rtl() else (inner, outer)


def _c(col: int, max_col: int) -> int:
    """Mirror a grid column index for RTL layouts."""
    return max_col - col if is_rtl() else col


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        self._main_queue: queue.Queue[Callable[[], None]] = queue.Queue()

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
        self._progress_view: str = "simple"
        self._download_items: list[dict] = []
        self._detail_rows: list[dict] = []
        self._current_item_index: int = 0
        self._total_items: int = 0
        self._concurrent_mode: bool = False

        self._custom_format_enabled: bool = False
        self._available_video_formats: list[dict] = []
        self._available_audio_formats: list[dict] = []

        self._available_subtitles: dict[str, list[dict]] = {"manual": [], "auto": []}
        self._subtitle_vars: dict[str, ctk.BooleanVar] = {}
        self._available_chapters: list[dict] = []
        self._chapter_vars: list[ctk.BooleanVar] = []

        self._tray = TrayManager(
            on_show=self._tray_show,
            on_quit=self._tray_quit,
        )
        self._tray_notified_minimize: bool = False

        self._build_ui()
        self._restore_state()
        self._restore_geometry()
        self._setup_dnd()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Unmap>", self._on_iconify)

        if settings.get("clipboard_monitor"):
            self._start_clipboard_monitor()

        self._tray.start()
        self._poll_tray()
        self._drain_main_queue()
        self.after(200, self._startup_checks)

    # -------------------------------------------------- Thread-safe dispatcher

    def _call_on_main(self, func: Callable[[], None]) -> None:
        """Schedule *func* to run on the main thread.

        Safe to call from any thread — never touches Tkinter directly.
        The main-thread poller ``_drain_main_queue`` picks it up.
        """
        self._main_queue.put(func)

    def _drain_main_queue(self) -> None:
        """Process pending callbacks from background threads (runs on main thread)."""
        while True:
            try:
                func = self._main_queue.get_nowait()
            except queue.Empty:
                break
            with contextlib.suppress(Exception):
                func()
        self.after(16, self._drain_main_queue)

    # --------------------------------------------------------- Startup checks
    def _startup_checks(self) -> None:
        ffmpeg_path = self._state.settings.get("ffmpeg_path", "")
        if not check_ffmpeg(ffmpeg_path):
            self._open_setup_wizard()
        else:
            self._ensure_ffmpeg_in_path()

        def _on_update(version: str | None, url: str | None) -> None:
            if version and url:
                self._call_on_main(lambda: self._show_update_banner(version, url))

        check_for_update(_on_update)

    def _open_setup_wizard(self) -> None:
        SetupWizard(self, self._state, on_complete=self._ensure_ffmpeg_in_path)

    def _ensure_ffmpeg_in_path(self) -> None:
        """Add the app bin dir to PATH if FFmpeg lives there."""
        bin_dir = get_bin_dir()
        bin_str = str(bin_dir)
        if bin_dir.exists() and bin_str not in os.environ.get("PATH", ""):
            os.environ["PATH"] = bin_str + os.pathsep + os.environ.get("PATH", "")

    def _show_update_banner(self, version: str, url: str) -> None:
        self._update_banner = ctk.CTkFrame(self._scroll_container, fg_color="#d1ecf1", corner_radius=6)
        self._update_banner.grid(row=0, column=0, padx=16, pady=(8, 0), sticky="ew")
        # cols 0=text(weight)  1=download  2=dismiss  → max_col=2
        self._update_banner.grid_columnconfigure(_c(0, 2), weight=1)

        ctk.CTkLabel(
            self._update_banner,
            text=t("update.banner", version=version),
            font=ctk.CTkFont(size=12),
            text_color="#0c5460",
            anchor=_anchor_start(),
        ).grid(row=0, column=_c(0, 2), padx=12, pady=8, sticky=_sticky_start())

        ctk.CTkButton(
            self._update_banner,
            text=t("update.download"),
            width=80,
            height=24,
            font=ctk.CTkFont(size=11),
            command=lambda: webbrowser.open(url),
        ).grid(row=0, column=_c(1, 2), padx=4, pady=8)

        ctk.CTkButton(
            self._update_banner,
            text=t("update.dismiss"),
            width=60,
            height=24,
            font=ctk.CTkFont(size=11),
            command=self._update_banner.destroy,
        ).grid(row=0, column=_c(2, 2), padx=_pad_end(8, 0), pady=8)

    def _shift_rows(self, start: int) -> None:
        """Banners insert at row 0; bump existing widgets down if needed."""
        pass

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll_container = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
        )
        self._scroll_container.grid(row=0, column=0, sticky="nsew")
        self._scroll_container.grid_columnconfigure(0, weight=1)

        self._build_url_frame(row=1)
        self._build_format_frame(row=2)
        self._build_output_frame(row=3)
        self._build_progress_frame(row=4)
        self._build_queue_panel(row=5)
        self._build_log_frame(row=6)
        self._build_status_bar(row=7)

    # -- URL input
    def _build_url_frame(self, row: int) -> None:
        self._url_frame = ctk.CTkFrame(self._scroll_container)
        self._url_frame.grid(row=row, column=0, padx=16, pady=(16, 8), sticky="ew")
        self._url_frame.grid_columnconfigure(0, weight=1)

        # header: cols 0=label  1=toggle(weight)  2=settings  → max_col=2
        header = ctk.CTkFrame(self._url_frame, fg_color="transparent")
        header.grid(row=0, column=0, padx=12, pady=(10, 0), sticky="ew")
        header.grid_columnconfigure(_c(1, 2), weight=1)

        ctk.CTkLabel(header, text=t("url.label"), font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=_c(0, 2), sticky=_sticky_start()
        )

        self._mode_var = ctk.StringVar(value=t("url.mode_single"))
        self._mode_toggle = ctk.CTkSegmentedButton(
            header, values=[t("url.mode_single"), t("url.mode_multiple")], variable=self._mode_var,
            command=self._on_mode_toggle, width=160,
        )
        self._mode_toggle.grid(row=0, column=_c(1, 2), padx=(8, 0), sticky=_sticky_start())

        self._settings_btn = ctk.CTkButton(
            header, text=t("url.settings"), width=80, command=self._open_settings,
        )
        self._settings_btn.grid(row=0, column=_c(2, 2), padx=_pad_end(0, 4))

        self._url_entry = ctk.CTkEntry(self._url_frame, font=ctk.CTkFont(size=13), placeholder_text=t("url.placeholder"))
        self._url_entry.bind("<Return>", lambda _: self._on_download())
        self._url_entry.bind("<KeyRelease>", lambda _: self.after(50, self._check_url_changed))

        self._url_textbox = ctk.CTkTextbox(self._url_frame, height=80, font=ctk.CTkFont(size=13))
        self._url_textbox.bind("<KeyRelease>", lambda _: self.after(50, self._check_url_changed))

        self._url_entry.grid(row=1, column=0, padx=12, pady=(6, 0), sticky="ew")

        # actions: cols 0=paste  1=preview  2=label(weight)  → max_col=2
        actions = ctk.CTkFrame(self._url_frame, fg_color="transparent")
        actions.grid(row=2, column=0, padx=12, pady=(6, 0), sticky="ew")
        actions.grid_columnconfigure(_c(2, 2), weight=1)

        self._paste_btn = ctk.CTkButton(actions, text=t("url.paste"), width=70, command=self._on_paste)
        self._paste_btn.grid(row=0, column=_c(0, 2), padx=_pad_start(0, 4))

        self._preview_btn = ctk.CTkButton(actions, text=t("url.preview"), width=70, command=self._on_preview)
        self._preview_btn.grid(row=0, column=_c(1, 2))

        self._preview_label = ctk.CTkLabel(
            actions, text="", anchor=_anchor_start(), font=ctk.CTkFont(size=12),
            wraplength=400,
        )
        self._preview_label.grid(row=0, column=_c(2, 2), padx=(8, 0), sticky="ew")

    # -- Format selection + download
    def _build_format_frame(self, row: int) -> None:
        frame = ctk.CTkFrame(self._scroll_container)
        frame.grid(row=row, column=0, padx=16, pady=4, sticky="ew")
        frame.grid_columnconfigure(_c(1, 3), weight=1)

        # row 0: cols 0=label  1=menu(weight)  2=download  3=cancel  → max_col=3
        ctk.CTkLabel(frame, text=t("format.label"), font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=_c(0, 3), padx=_pad_start(12, 6), pady=(12, 4)
        )

        format_names = list(FORMAT_PRESETS.keys())
        self._format_var = ctk.StringVar(value=format_names[0])
        self._format_menu = ctk.CTkOptionMenu(
            frame, variable=self._format_var, values=format_names, width=240
        )
        self._format_menu.grid(row=0, column=_c(1, 3), padx=4, pady=(12, 4), sticky=_sticky_start())

        self._download_btn = ctk.CTkButton(
            frame,
            text=t("format.download"),
            width=130,
            fg_color="#28a745",
            hover_color="#218838",
            command=self._on_download,
        )
        self._download_btn.grid(row=0, column=_c(2, 3), padx=(4, 6), pady=(12, 4))

        self._cancel_btn = ctk.CTkButton(
            frame,
            text=t("format.cancel"),
            width=80,
            fg_color="#dc3545",
            hover_color="#c82333",
            state="disabled",
            command=self._on_cancel,
        )
        self._cancel_btn.grid(row=0, column=_c(3, 3), padx=_pad_end(12, 4), pady=(12, 4))

        # Custom format checkbox (always visible in row 1)
        self._custom_format_var = ctk.BooleanVar(value=False)
        self._custom_format_checkbox = ctk.CTkCheckBox(
            frame, text=t("format.custom_format"),
            variable=self._custom_format_var,
            font=ctk.CTkFont(size=13), command=self._on_custom_format_toggled,
        )
        self._custom_format_checkbox.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 4), sticky=_sticky_start())

        # Custom format picker (hidden until checkbox is checked)
        # cols 0=vlabel  1=vmenu  2=alabel  3=amenu  4=status(weight) → max_col=4
        self._custom_format_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._custom_format_frame.grid_columnconfigure(_c(4, 4), weight=1)

        ctk.CTkLabel(
            self._custom_format_frame, text=t("format.video"), font=ctk.CTkFont(size=12),
        ).grid(row=0, column=_c(0, 4), padx=(0, 4))

        self._video_format_var = ctk.StringVar(value="")
        self._video_format_menu = ctk.CTkOptionMenu(
            self._custom_format_frame, variable=self._video_format_var,
            values=[t("format.preview_first")], width=260, state="disabled",
        )
        self._video_format_menu.grid(row=0, column=_c(1, 4), padx=(0, 12))

        ctk.CTkLabel(
            self._custom_format_frame, text=t("format.audio"), font=ctk.CTkFont(size=12),
        ).grid(row=0, column=_c(2, 4), padx=(0, 4))

        self._audio_format_var = ctk.StringVar(value="")
        self._audio_format_menu = ctk.CTkOptionMenu(
            self._custom_format_frame, variable=self._audio_format_var,
            values=[t("format.preview_first")], width=200, state="disabled",
        )
        self._audio_format_menu.grid(row=0, column=_c(3, 4), padx=(0, 8))

        self._format_status_label = ctk.CTkLabel(
            self._custom_format_frame, text="", font=ctk.CTkFont(size=11),
            text_color="gray", anchor=_anchor_start(),
        )
        self._format_status_label.grid(row=0, column=_c(4, 4), padx=(4, 0), sticky=_sticky_start())

        # Options row: cols 0=split  1=section  2=queue  3=playlist(weight)  → max_col=3
        opts = ctk.CTkFrame(frame, fg_color="transparent")
        opts.grid(row=3, column=0, columnspan=4, padx=12, pady=(0, 10), sticky="ew")
        opts.grid_columnconfigure(_c(3, 3), weight=1)

        self._split_chapters_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opts, text=t("format.split_chapters"), variable=self._split_chapters_var,
            font=ctk.CTkFont(size=13),
        ).grid(row=0, column=_c(0, 3), padx=_pad_start(0, 16))

        self._section_var = ctk.BooleanVar(value=False)
        self._section_checkbox = ctk.CTkCheckBox(
            opts, text=t("format.download_section"), variable=self._section_var,
            font=ctk.CTkFont(size=13), command=self._on_section_toggled,
        )
        self._section_checkbox.grid(row=0, column=_c(1, 3), padx=_pad_start(0, 8))

        self._playlist_label = ctk.CTkLabel(
            opts, text="", anchor=_sticky_end(), font=ctk.CTkFont(size=12),
        )
        self._playlist_label.grid(row=0, column=_c(3, 3), sticky=_sticky_end())

        self._queue_label = ctk.CTkLabel(
            opts, text="", anchor=_sticky_end(), font=ctk.CTkFont(size=12), text_color="gray",
        )
        self._queue_label.grid(row=0, column=_c(2, 3), padx=(8, 8))

        # Section frame: cols 0=startlbl  1=startentry  2=endlbl  3=endentry  4=error(weight)
        self._section_frame = ctk.CTkFrame(opts, fg_color="transparent")
        self._section_frame.grid_columnconfigure(_c(4, 4), weight=1)

        ctk.CTkLabel(
            self._section_frame, text=t("format.section_start"), font=ctk.CTkFont(size=12),
        ).grid(row=0, column=_c(0, 4), padx=(0, 4))

        self._section_start_entry = ctk.CTkEntry(
            self._section_frame, width=90, font=ctk.CTkFont(size=12),
            placeholder_text=t("format.section_start_placeholder"),
        )
        self._section_start_entry.grid(row=0, column=_c(1, 4), padx=(0, 12))

        ctk.CTkLabel(
            self._section_frame, text=t("format.section_end"), font=ctk.CTkFont(size=12),
        ).grid(row=0, column=_c(2, 4), padx=(0, 4))

        self._section_end_entry = ctk.CTkEntry(
            self._section_frame, width=90, font=ctk.CTkFont(size=12),
            placeholder_text=t("format.section_end_placeholder"),
        )
        self._section_end_entry.grid(row=0, column=_c(3, 4), padx=(0, 12))

        self._section_error_label = ctk.CTkLabel(
            self._section_frame, text="", font=ctk.CTkFont(size=11),
            text_color="#dc3545", anchor=_anchor_start(),
        )
        self._section_error_label.grid(row=0, column=_c(4, 4), sticky=_sticky_start())

        # Post-processing row: cols 0=cvtlbl  1=cvtmenu  2=sublbl  3=submenu  4=burn
        pp_frame = ctk.CTkFrame(frame, fg_color="transparent")
        pp_frame.grid(row=4, column=0, columnspan=4, padx=12, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(
            pp_frame, text=t("format.convert"), font=ctk.CTkFont(size=12),
        ).grid(row=0, column=_c(0, 4), padx=(0, 4))

        convert_values = [
            "None", "MP4", "MKV", "WebM", "MP3", "AAC", "FLAC", "WAV", "OGG",
        ]
        settings = self._state.settings
        current_convert = settings.get("convert_format", "")
        convert_display = current_convert.upper() if current_convert else "None"
        if convert_display not in convert_values:
            convert_display = "None"
        self._convert_var = ctk.StringVar(value=convert_display)
        self._convert_menu = ctk.CTkOptionMenu(
            pp_frame, variable=self._convert_var, values=convert_values,
            width=90, command=self._on_convert_changed,
        )
        self._convert_menu.grid(row=0, column=_c(1, 4), padx=(0, 16))

        ctk.CTkLabel(
            pp_frame, text=t("format.subs"), font=ctk.CTkFont(size=12),
        ).grid(row=0, column=_c(2, 4), padx=(0, 4))

        sub_values = ["None", "Embed", "File"]
        current_sub = settings.get("subtitle_mode", "")
        sub_display = {"embed": "Embed", "file": "File"}.get(current_sub, "None")
        self._subtitle_mode_var = ctk.StringVar(value=sub_display)
        self._subtitle_mode_menu = ctk.CTkOptionMenu(
            pp_frame, variable=self._subtitle_mode_var, values=sub_values,
            width=90, command=self._on_subtitle_mode_changed,
        )
        self._subtitle_mode_menu.grid(row=0, column=_c(3, 4), padx=(0, 8))

        self._burn_sub_var = ctk.BooleanVar(value=settings.get("subtitle_burn", False))
        self._burn_sub_checkbox = ctk.CTkCheckBox(
            pp_frame, text=t("format.burn_subs"), variable=self._burn_sub_var,
            font=ctk.CTkFont(size=12),
            command=lambda: self._state.save_settings(subtitle_burn=self._burn_sub_var.get()),
        )
        self._burn_sub_checkbox.grid(row=0, column=_c(4, 4), padx=(0, 8))

        # Subtitle summary row: cols 0=label(weight)  1=edit  → max_col=1
        self._subtitle_summary_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._subtitle_summary_frame.grid_columnconfigure(_c(0, 1), weight=1)

        self._subtitle_summary_label = ctk.CTkLabel(
            self._subtitle_summary_frame, text=t("format.subtitle_none"),
            font=ctk.CTkFont(size=12), anchor=_anchor_start(),
        )
        self._subtitle_summary_label.grid(row=0, column=_c(0, 1), sticky=_sticky_start())

        self._subtitle_edit_btn = ctk.CTkButton(
            self._subtitle_summary_frame, text=t("format.edit"), width=60, height=24,
            font=ctk.CTkFont(size=11), command=self._open_subtitle_picker_dialog,
        )
        self._subtitle_edit_btn.grid(row=0, column=_c(1, 1), padx=_pad_end(0, 8))

        self._subtitle_select_all_var = ctk.BooleanVar(value=False)
        self._subtitle_dialog: ctk.CTkToplevel | None = None

        # Chapter summary row: cols 0=label(weight)  1=edit  → max_col=1
        self._chapter_summary_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self._chapter_summary_frame.grid_columnconfigure(_c(0, 1), weight=1)

        self._chapter_summary_label = ctk.CTkLabel(
            self._chapter_summary_frame, text=t("format.chapters_all"),
            font=ctk.CTkFont(size=12), anchor=_anchor_start(),
        )
        self._chapter_summary_label.grid(row=0, column=_c(0, 1), sticky=_sticky_start())

        self._chapter_edit_btn = ctk.CTkButton(
            self._chapter_summary_frame, text=t("format.edit"), width=60, height=24,
            font=ctk.CTkFont(size=11), command=self._open_chapter_picker_dialog,
        )
        self._chapter_edit_btn.grid(row=0, column=_c(1, 1), padx=_pad_end(0, 8))

        self._chapter_select_all_var = ctk.BooleanVar(value=True)
        self._chapter_dialog: ctk.CTkToplevel | None = None

    # -- Output folder
    def _build_output_frame(self, row: int) -> None:
        frame = ctk.CTkFrame(self._scroll_container)
        frame.grid(row=row, column=0, padx=16, pady=4, sticky="ew")
        # cols 0=label  1=menu(weight)  2=browse  → max_col=2
        frame.grid_columnconfigure(_c(1, 2), weight=1)

        ctk.CTkLabel(frame, text=t("output.label"), font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=_c(0, 2), padx=_pad_start(12, 6), pady=12
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

    # -- Progress bar
    def _build_progress_frame(self, row: int) -> None:
        self._progress_frame = ctk.CTkFrame(self._scroll_container)
        self._progress_frame.grid(row=row, column=0, padx=16, pady=4, sticky="ew")
        self._progress_frame.grid_columnconfigure(0, weight=1)

        # header: cols 0=overall(weight)  1=(toggle placeholder)  2=(placeholder)  3=open folder
        progress_header = ctk.CTkFrame(self._progress_frame, fg_color="transparent")
        progress_header.grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 2), sticky="ew")
        progress_header.grid_columnconfigure(_c(0, 3), weight=1)

        self._overall_label = ctk.CTkLabel(
            progress_header, text="", anchor=_anchor_start(), font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._overall_label.grid(row=0, column=_c(0, 3), sticky=_sticky_start())

        self._progress_view_var = ctk.StringVar(value=t("progress.view_simple"))
        self._progress_view_toggle = ctk.CTkSegmentedButton(
            progress_header, values=[t("progress.view_simple"), t("progress.view_detailed")], variable=self._progress_view_var,
            command=self._on_progress_view_toggle, width=150,
        )

        self._open_folder_btn = ctk.CTkButton(
            progress_header, text=t("progress.open_folder"), width=90,
            state="disabled", command=self._on_open_folder,
        )
        self._open_folder_btn.grid(row=0, column=_c(3, 3), padx=_pad_end(0, 4))

        # Simple progress view
        self._simple_progress_frame = ctk.CTkFrame(self._progress_frame, fg_color="transparent")
        self._simple_progress_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        self._simple_progress_frame.grid_columnconfigure(0, weight=1)

        self._title_label = ctk.CTkLabel(
            self._simple_progress_frame, text=t("progress.no_video"), anchor=_anchor_start(), font=ctk.CTkFont(size=13)
        )
        self._title_label.grid(row=0, column=0, padx=12, pady=(2, 2), sticky="ew")

        self._progress_bar = ctk.CTkProgressBar(self._simple_progress_frame)
        self._progress_bar.grid(row=1, column=0, padx=12, pady=4, sticky="ew")
        self._progress_bar.set(0)

        self._progress_detail = ctk.CTkLabel(
            self._simple_progress_frame, text=t("progress.initial"), anchor=_anchor_start(), font=ctk.CTkFont(size=12)
        )
        self._progress_detail.grid(row=2, column=0, padx=12, pady=(2, 10), sticky="ew")

        # Detailed progress view (hidden by default)
        self._detailed_progress_frame = ctk.CTkScrollableFrame(
            self._progress_frame, height=150,
        )

    def _on_progress_view_toggle(self, value: str) -> None:
        view = "detailed" if value == t("progress.view_detailed") else "simple"
        if view == self._progress_view:
            return
        self._progress_view = view
        self._switch_progress_view(view)

    def _switch_progress_view(self, view: str) -> None:
        self._progress_view = view
        label = t("progress.view_detailed") if view == "detailed" else t("progress.view_simple")
        self._progress_view_var.set(label)
        if view == "simple":
            self._detailed_progress_frame.grid_forget()
            self._simple_progress_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        else:
            self._simple_progress_frame.grid_forget()
            self._detailed_progress_frame.grid(row=1, column=0, columnspan=2, padx=12, pady=(2, 10), sticky="nsew")
            self._rebuild_detail_rows()

    # -- Queue panel
    def _build_queue_panel(self, row: int) -> None:
        self._queue_panel = ctk.CTkFrame(self._scroll_container)
        self._queue_panel.grid(row=row, column=0, padx=16, pady=4, sticky="ew")
        self._queue_panel.grid_columnconfigure(0, weight=1)

        # header: cols 0=title(weight)  1=clear  2=start  → max_col=2
        header = ctk.CTkFrame(self._queue_panel, fg_color="transparent")
        header.grid(row=0, column=0, padx=12, pady=(8, 4), sticky="ew")
        header.grid_columnconfigure(_c(0, 2), weight=1)

        self._queue_header_label = ctk.CTkLabel(
            header, text=t("queue.title"), font=ctk.CTkFont(size=13, weight="bold"), anchor=_anchor_start(),
        )
        self._queue_header_label.grid(row=0, column=_c(0, 2), sticky=_sticky_start())

        self._queue_clear_btn = ctk.CTkButton(
            header, text=t("queue.clear"), width=60, height=24,
            font=ctk.CTkFont(size=11),
            fg_color="#dc3545", hover_color="#c82333",
            command=self._clear_queue,
        )

        self._queue_start_btn = ctk.CTkButton(
            header, text=t("queue.start"), width=90, height=24,
            font=ctk.CTkFont(size=11),
            fg_color="#28a745", hover_color="#218838",
            command=self._start_queue,
        )

        self._queue_empty_label = ctk.CTkLabel(
            self._queue_panel, text=t("queue.empty"),
            font=ctk.CTkFont(size=12), text_color="gray", anchor=_anchor_start(),
        )
        self._queue_empty_label.grid(row=1, column=0, padx=12, pady=(0, 8), sticky=_sticky_start())

        self._queue_scroll = ctk.CTkScrollableFrame(self._queue_panel, height=100)
        self._queue_scroll.grid_columnconfigure(_c(1, 2), weight=1)

        self._queue_rows: list[dict] = []

    def _rebuild_queue_rows(self) -> None:
        """Clear and rebuild all rows in the queue panel."""
        for widget in self._queue_scroll.winfo_children():
            widget.destroy()
        self._queue_rows = []

        if not self._queue:
            self._queue_header_label.configure(text=t("queue.title"))
            self._queue_clear_btn.grid_forget()
            self._queue_start_btn.grid_forget()
            self._queue_scroll.grid_forget()
            self._queue_empty_label.grid(row=1, column=0, padx=12, pady=(0, 8), sticky=_sticky_start())
            return

        self._queue_empty_label.grid_forget()
        self._queue_header_label.configure(text=t("queue.title_count", count=len(self._queue)))
        self._queue_clear_btn.grid(row=0, column=_c(1, 2), padx=(4, 0))
        self._queue_start_btn.grid(row=0, column=_c(2, 2), padx=(4, 0))
        self._queue_scroll.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")

        # each row: cols 0=idx  1=title(weight)  2=buttons  → max_col=2
        for i, entry in enumerate(self._queue):
            row_frame = ctk.CTkFrame(self._queue_scroll, fg_color="transparent")
            row_frame.grid(row=i, column=0, sticky="ew", pady=2)
            row_frame.grid_columnconfigure(_c(1, 2), weight=1)

            idx_label = ctk.CTkLabel(
                row_frame, text=f"{i + 1}.", width=24,
                font=ctk.CTkFont(size=12),
            )
            idx_label.grid(row=0, column=_c(0, 2), padx=(4, 4))

            url_count = len(entry.get("urls", []))
            first_url = truncate_filename(entry["urls"][0], 35) if entry.get("urls") else "?"
            fmt = entry.get("format_key", "Best")
            if url_count == 1:
                display = t("queue.display_single", url=first_url, fmt=fmt)
            else:
                display = t("queue.display_multi", url=first_url, extra=url_count - 1, fmt=fmt)

            title_label = ctk.CTkLabel(
                row_frame, text=display, anchor=_anchor_start(),
                font=ctk.CTkFont(size=12),
            )
            title_label.grid(row=0, column=_c(1, 2), sticky="ew", padx=(0, 4))

            btn_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            btn_frame.grid(row=0, column=_c(2, 2), padx=(0, 4))

            up_btn = ctk.CTkButton(
                btn_frame, text="\u25B2", width=28, height=22,
                font=ctk.CTkFont(size=10),
                command=lambda idx=i: self._move_queue_item(idx, -1),
                state="normal" if i > 0 else "disabled",
            )
            up_btn.grid(row=0, column=0, padx=1)

            down_btn = ctk.CTkButton(
                btn_frame, text="\u25BC", width=28, height=22,
                font=ctk.CTkFont(size=10),
                command=lambda idx=i: self._move_queue_item(idx, 1),
                state="normal" if i < len(self._queue) - 1 else "disabled",
            )
            down_btn.grid(row=0, column=1, padx=1)

            remove_btn = ctk.CTkButton(
                btn_frame, text="\u2715", width=28, height=22,
                font=ctk.CTkFont(size=10),
                fg_color="#dc3545", hover_color="#c82333",
                command=lambda idx=i: self._remove_queue_item(idx),
            )
            remove_btn.grid(row=0, column=2, padx=1)

            self._queue_rows.append({
                "frame": row_frame,
                "idx_label": idx_label,
                "title_label": title_label,
                "up_btn": up_btn,
                "down_btn": down_btn,
                "remove_btn": remove_btn,
            })

    def _clear_queue(self) -> None:
        self._queue.clear()
        self._persist_queue()
        self._update_queue_label()
        self._rebuild_queue_rows()
        self._log(t("log.queue_cleared"))

    def _start_queue(self) -> None:
        """Start processing the queue if not already downloading."""
        if not self._queue:
            return
        if self._manager.is_busy:
            self._log(t("log.already_downloading"))
            return
        self._process_queue()

    def _move_queue_item(self, index: int, direction: int) -> None:
        """Swap the queue item at index with its neighbor in the given direction."""
        new_index = index + direction
        if new_index < 0 or new_index >= len(self._queue):
            return
        self._queue[index], self._queue[new_index] = self._queue[new_index], self._queue[index]
        self._persist_queue()
        self._rebuild_queue_rows()

    def _remove_queue_item(self, index: int) -> None:
        if 0 <= index < len(self._queue):
            removed = self._queue.pop(index)
            urls = removed.get("urls", [])
            self._persist_queue()
            self._update_queue_label()
            self._rebuild_queue_rows()
            self._log(t("log.removed_from_queue", url=truncate_filename(urls[0], 40) if urls else "?"))

    # -- Log / status area
    def _build_log_frame(self, row: int) -> None:
        frame = ctk.CTkFrame(self._scroll_container)
        frame.grid(row=row, column=0, padx=16, pady=(4, 4), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        # header: cols 0=title(weight)  1=toggle  → max_col=1
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, padx=8, pady=(8, 0), sticky="ew")
        header.grid_columnconfigure(_c(0, 1), weight=1)

        ctk.CTkLabel(header, text=t("log.title"), font=ctk.CTkFont(size=12, weight="bold"), anchor=_anchor_start()).grid(
            row=0, column=_c(0, 1), sticky=_sticky_start()
        )

        self._history_toggle_btn = ctk.CTkButton(
            header, text=t("log.show_history"), width=100, height=24,
            font=ctk.CTkFont(size=11), command=self._toggle_history,
        )
        self._history_toggle_btn.grid(row=0, column=_c(1, 1), padx=_pad_end(0, 4))

        self._log_box = ctk.CTkTextbox(frame, height=100, state="disabled", font=ctk.CTkFont(size=12))
        self._log_box.grid(row=1, column=0, padx=8, pady=(4, 8), sticky="nsew")

        self._history_frame = ctk.CTkFrame(frame)
        self._history_textbox = ctk.CTkTextbox(
            self._history_frame, height=100, state="disabled", font=ctk.CTkFont(size=12),
        )
        self._history_textbox.pack(fill="both", expand=True, padx=8, pady=8)

    # -- Status bar
    def _build_status_bar(self, row: int) -> None:
        bar = ctk.CTkFrame(self._scroll_container, fg_color="transparent")
        bar.grid(row=row, column=0, padx=20, pady=(0, 6), sticky="ew")
        # cols 0=stats(weight)  1=version  → max_col=1
        bar.grid_columnconfigure(_c(0, 1), weight=1)

        self._status_bar = ctk.CTkLabel(
            bar, text="", anchor=_anchor_start(), font=ctk.CTkFont(size=11), text_color="gray",
        )
        self._status_bar.grid(row=0, column=_c(0, 1), sticky=_sticky_start())

        self._version_label = ctk.CTkLabel(
            bar, text=f"v{APP_VERSION}", anchor=_sticky_end(),
            font=ctk.CTkFont(size=10), text_color="gray",
        )
        self._version_label.grid(row=0, column=_c(1, 1), sticky=_sticky_end())

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

    # ----------------------------------------------------------- Drag-and-drop
    def _setup_dnd(self) -> None:
        if not _HAS_DND:
            return
        try:
            self._url_textbox.drop_target_register(DND_TEXT)
            self._url_textbox.dnd_bind("<<Drop>>", self._on_dnd_drop)
            self._url_entry.drop_target_register(DND_TEXT)
            self._url_entry.dnd_bind("<<Drop>>", self._on_dnd_drop)
        except Exception:
            pass

    def _on_dnd_drop(self, event: object) -> None:
        text = getattr(event, "data", "").strip()
        if not text:
            return
        if self._input_mode == "single" and "\n" in text:
            self._auto_switch_to_multiple(text)
            return
        if self._input_mode == "single":
            self._url_entry.delete(0, "end")
            self._url_entry.insert(0, text.split("\n")[0].strip())
        else:
            current = self._url_textbox.get("1.0", "end").strip()
            if current:
                self._url_textbox.insert("end", "\n" + text)
            else:
                self._url_textbox.delete("1.0", "end")
                self._url_textbox.insert("1.0", text)

    # ---------------------------------------------------- Detailed progress
    def _init_download_items(self, urls: list[str]) -> None:
        """Initialize per-item tracking for a batch download."""
        self._download_items = [
            {
                "url": u, "status": "queued", "progress": 0.0, "title": "",
                "error": None, "accumulated_bytes": 0,
            }
            for u in urls
        ]
        self._detail_rows = []
        self._current_item_index = 0
        self._total_items = len(urls)
        if self._input_mode == "multiple":
            self._overall_label.configure(text=t("progress.overall", done=0, total=self._total_items))
        if self._progress_view == "detailed":
            self._rebuild_detail_rows()

    def _rebuild_detail_rows(self) -> None:
        """Rebuild all rows in the detailed scrollable frame from _download_items."""
        for widget in self._detailed_progress_frame.winfo_children():
            widget.destroy()
        self._detail_rows = []
        self._detailed_progress_frame.grid_columnconfigure(_c(1, 4), weight=1)

        # each row: cols 0=icon  1=title(weight)  2=bar  3=info  4=retry  → max_col=4
        for i, item in enumerate(self._download_items):
            row_frame = ctk.CTkFrame(self._detailed_progress_frame, fg_color="transparent")
            row_frame.grid(row=i, column=0, columnspan=5, sticky="ew", pady=2)
            row_frame.grid_columnconfigure(_c(1, 4), weight=1)

            status_label = ctk.CTkLabel(
                row_frame, text=self._status_icon(item["status"]), width=24,
                font=ctk.CTkFont(size=13),
            )
            status_label.grid(row=0, column=_c(0, 4), padx=(4, 4))

            display = item["title"] or truncate_filename(item["url"], 40)
            title_label = ctk.CTkLabel(
                row_frame, text=display, anchor=_anchor_start(),
                font=ctk.CTkFont(size=12),
            )
            title_label.grid(row=0, column=_c(1, 4), sticky="ew", padx=(0, 4))

            bar = ctk.CTkProgressBar(row_frame, width=120, height=12)
            bar.grid(row=0, column=_c(2, 4), padx=(0, 4))
            bar.set(item["progress"])

            info_label = ctk.CTkLabel(
                row_frame, text=self._status_text(item), anchor=_sticky_end(),
                font=ctk.CTkFont(size=11), width=60,
            )
            info_label.grid(row=0, column=_c(3, 4), padx=(0, 4))

            retry_btn = ctk.CTkButton(
                row_frame, text=t("progress.retry"), width=50, height=22,
                font=ctk.CTkFont(size=10),
                fg_color="#dc3545", hover_color="#c82333",
                command=lambda idx=i: self._retry_item(idx),
            )
            if item["status"] == "failed":
                retry_btn.grid(row=0, column=_c(4, 4), padx=(0, 4))

            self._detail_rows.append({
                "frame": row_frame,
                "status_label": status_label,
                "title_label": title_label,
                "bar": bar,
                "info_label": info_label,
                "retry_btn": retry_btn,
            })

    def _update_detail_row(self, index: int) -> None:
        """Update a single row in the detailed view without rebuilding everything."""
        if index >= len(self._detail_rows) or index >= len(self._download_items):
            return
        item = self._download_items[index]
        row = self._detail_rows[index]

        row["status_label"].configure(text=self._status_icon(item["status"]))
        display = item["title"] or truncate_filename(item["url"], 40)
        row["title_label"].configure(text=display)
        row["bar"].set(item["progress"])
        row["info_label"].configure(text=self._status_text(item))

        if item["status"] == "failed":
            row["retry_btn"].grid(row=0, column=_c(4, 4), padx=(0, 4))
        else:
            row["retry_btn"].grid_forget()

    @staticmethod
    def _status_icon(status: str) -> str:
        return {"queued": "[ ]", "downloading": "[>]", "done": "[v]", "failed": "[x]"}.get(status, "[ ]")

    @staticmethod
    def _status_text(item: dict) -> str:
        status = item["status"]
        if status == "queued":
            return t("progress.status_queued")
        if status == "downloading":
            pct = item["progress"] * 100
            return f"{pct:.0f}%"
        if status == "done":
            return t("progress.status_done")
        if status == "failed":
            return t("progress.status_failed")
        return ""

    def _retry_item(self, index: int) -> None:
        """Re-download a single failed item."""
        if index >= len(self._download_items):
            return
        item = self._download_items[index]
        if item["status"] != "failed":
            return
        if self._manager.is_busy:
            entry = self._build_queue_entry([item["url"]], self._is_playlist_download)
            self._queue.append(entry)
            self._persist_queue()
            self._update_queue_label()
            self._rebuild_queue_rows()
            self._log(t("log.queued_retry", url=truncate_filename(item["url"], 50)))
            return

        item["status"] = "queued"
        item["progress"] = 0.0
        item["error"] = None
        if self._progress_view == "detailed":
            self._update_detail_row(index)

        self._retry_single_url(item["url"], index)

    def _retry_single_url(self, url: str, item_index: int) -> None:
        """Download a single URL as a retry, updating the item at item_index."""
        os.makedirs(self._output_dir, exist_ok=True)

        format_key = self._format_var.get()
        split_chapters = self._split_chapters_var.get()
        custom_format_str = self._get_custom_format_string() if self._custom_format_enabled else ""

        self._download_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")

        def on_progress(data: dict) -> None:
            self._call_on_main(lambda d=data: self._update_retry_progress(d, item_index))

        def on_item_done(index: int, total: int, error: str | None) -> None:
            self._call_on_main(lambda: self._retry_item_finished(item_index, error))

        def on_done(error: str | None) -> None:
            self._call_on_main(lambda: self._download_finished(error))

        self._manager.download_batch(
            [url], format_key, self._output_dir,
            split_chapters=split_chapters,
            playlist=self._is_playlist_download,
            progress_callback=on_progress,
            item_done_callback=on_item_done,
            done_callback=on_done,
            settings=self._state.settings,
            format_string=custom_format_str,
        )

    def _update_retry_progress(self, data: dict, item_index: int) -> None:
        if item_index >= len(self._download_items):
            return
        item = self._download_items[item_index]
        item["status"] = "downloading"
        title = data.get("title")
        if title:
            item["title"] = title

        total = data["total_bytes"]
        downloaded = data["downloaded_bytes"]
        if total and total > 0:
            item["progress"] = downloaded / total
        if data["status"] == "finished":
            item["progress"] = 1.0

        if self._progress_view == "detailed":
            self._update_detail_row(item_index)
        self._update_progress(data)

    def _retry_item_finished(self, item_index: int, error: str | None) -> None:
        if item_index >= len(self._download_items):
            return
        item = self._download_items[item_index]
        if error:
            item["status"] = "failed"
            item["error"] = error
            self._log(t("log.retry_failed", error=error))
            url = item["url"]
            self._state.record_failed(title=item.get("title", ""), url=url)
        else:
            item["status"] = "done"
            item["progress"] = 1.0
            self._log(t("log.retry_done", title=item.get("title") or item["url"]))
            self._state.record_download(
                bytes_downloaded=self._accumulated_bytes,
                is_audio=self._is_audio_download,
                is_playlist=self._is_playlist_download,
                title=item.get("title", ""),
                url=item["url"],
            )
            self._accumulated_bytes = 0
            self._refresh_status_bar()

        if self._progress_view == "detailed":
            self._update_detail_row(item_index)

    # --------------------------------------------------------- Settings window
    def _open_settings(self) -> None:
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.focus()
            return
        self._settings_window = SettingsWindow(
            self,
            self._state,
            on_clipboard_changed=self._on_clipboard_setting_changed,
            on_language_changed=self._on_language_changed,
        )

    def _on_language_changed(self, code: str) -> None:
        """Reload the i18n strings and rebuild the entire UI live."""
        load_language(code)
        self.title(t("app.title"))
        for widget in self.winfo_children():
            widget.destroy()
        self._build_ui()
        self._restore_state()
        self._setup_dnd()
        self._tray.update_tooltip(t("tray.tooltip"))
        self._refresh_status_bar()

    def _on_clipboard_setting_changed(self, enabled: bool) -> None:
        if enabled:
            self._start_clipboard_monitor()
        else:
            self._stop_clipboard_monitor()

    # ----------------------------------------------------------- Mode toggle
    def _on_mode_toggle(self, value: str) -> None:
        mode = "multiple" if value == t("url.mode_multiple") else "single"
        if mode == self._input_mode:
            return
        self._switch_mode(mode)

    def _switch_mode(self, mode: str) -> None:
        old_mode = self._input_mode
        self._input_mode = mode
        label = t("url.mode_multiple") if mode == "multiple" else t("url.mode_single")
        self._mode_var.set(label)

        if old_mode == "single":
            text = self._url_entry.get().strip()
        else:
            text = self._url_textbox.get("1.0", "end").strip()

        if mode == "single":
            self._url_textbox.grid_forget()
            self._url_entry.grid(row=1, column=0, padx=12, pady=(6, 0), sticky="ew")
            self._url_entry.delete(0, "end")
            first_line = text.split("\n")[0].strip() if text else ""
            if first_line:
                self._url_entry.insert(0, first_line)
            self._progress_view_toggle.grid_forget()
        else:
            self._url_entry.grid_forget()
            self._url_textbox.grid(row=1, column=0, padx=12, pady=(6, 0), sticky="ew")
            self._url_textbox.delete("1.0", "end")
            if text:
                self._url_textbox.insert("1.0", text)
            self._progress_view_toggle.grid(row=0, column=_c(2, 3), padx=(8, 0))

        self._update_section_visibility()

    def _auto_switch_to_multiple(self, text: str) -> None:
        """If text contains multiple lines, switch to Multiple mode and populate."""
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        if len(lines) > 1 and self._input_mode == "single":
            self._url_entry.delete(0, "end")
            self._switch_mode("multiple")
            self._url_textbox.delete("1.0", "end")
            self._url_textbox.insert("1.0", "\n".join(lines))

    # ------------------------------------------------- Custom format picker
    def _on_custom_format_toggled(self) -> None:
        enabled = self._custom_format_var.get()
        self._custom_format_enabled = enabled
        if enabled:
            self._custom_format_frame.grid(
                row=2, column=0, columnspan=4, padx=12, pady=(4, 4), sticky="ew",
            )
            self._format_menu.configure(state="disabled")
            has_formats = bool(self._available_video_formats or self._available_audio_formats)
            if has_formats:
                self._video_format_menu.configure(state="normal")
                self._audio_format_menu.configure(state="normal")
            else:
                self._format_status_label.configure(
                    text=t("format.load_formats_hint"),
                    text_color="#e0a800",
                )
        else:
            self._custom_format_frame.grid_forget()
            self._format_menu.configure(state="normal")

    def _populate_format_picker(self, info: dict) -> None:
        """Parse formats from info_dict and populate the custom format dropdowns."""
        video_formats, audio_formats = parse_formats(info)
        self._available_video_formats = video_formats
        self._available_audio_formats = audio_formats

        if video_formats:
            labels = [f["label"] for f in video_formats]
            self._video_format_menu.configure(values=labels, state="normal")
            self._video_format_var.set(labels[0])
        else:
            self._video_format_menu.configure(values=[t("format.none_available")], state="disabled")
            self._video_format_var.set(t("format.none_available"))

        if audio_formats:
            labels = [f["label"] for f in audio_formats]
            self._audio_format_menu.configure(values=labels, state="normal")
            self._audio_format_var.set(labels[0])
        else:
            self._audio_format_menu.configure(values=[t("format.none_available")], state="disabled")
            self._audio_format_var.set(t("format.none_available"))

        count_str = t("format.count", video=len(video_formats), audio=len(audio_formats))
        self._format_status_label.configure(text=count_str, text_color="#17a2b8")

    def _get_custom_format_string(self) -> str:
        """Build a yt-dlp format string from the currently selected custom formats."""
        video_id = ""
        audio_id = ""

        video_label = self._video_format_var.get()
        for f in self._available_video_formats:
            if f["label"] == video_label:
                video_id = f["format_id"]
                break

        audio_label = self._audio_format_var.get()
        for f in self._available_audio_formats:
            if f["label"] == audio_label:
                audio_id = f["format_id"]
                break

        return build_format_string(video_id, audio_id)

    # ------------------------------------------------ Post-processing callbacks
    def _on_convert_changed(self, value: str) -> None:
        fmt = "" if value == "None" else value.lower()
        self._state.save_settings(convert_format=fmt)

    def _on_subtitle_mode_changed(self, value: str) -> None:
        mode = {"Embed": "embed", "File": "file"}.get(value, "")
        self._state.save_settings(subtitle_mode=mode)

    # ------------------------------------------------- Metadata pickers
    def _check_url_changed(self) -> None:
        """Hide pickers only when URL content actually changes (not on modifier keys)."""
        current = self._get_urls()
        current_str = "\n".join(current)
        if not hasattr(self, "_last_preview_url_str"):
            self._last_preview_url_str = ""
        if current_str != self._last_preview_url_str and self._last_preview_url_str:
            self._clear_metadata_pickers()

    def _clear_metadata_pickers(self) -> None:
        """Hide subtitle and chapter pickers when URL changes."""
        self._last_preview_url_str = ""
        if self._available_subtitles["manual"] or self._available_subtitles["auto"]:
            self._hide_subtitle_picker()
        if self._available_chapters:
            self._hide_chapter_picker()

    # ------------------------------------------------- Subtitle picker
    def _populate_subtitle_picker(self, info: dict) -> None:
        """Parse subtitles from info_dict and show summary row."""
        subs = parse_subtitles(info)
        self._available_subtitles = subs
        self._subtitle_vars.clear()

        has_any = bool(subs["manual"] or subs["auto"])
        if not has_any:
            self._subtitle_summary_frame.grid_forget()
            return

        default_langs = [
            lang.strip()
            for lang in self._state.settings.get("subtitle_languages", "en").split(",")
            if lang.strip()
        ]

        for entry in subs["manual"]:
            code = entry["code"]
            pre_selected = code in default_langs or "all" in default_langs
            var = ctk.BooleanVar(value=pre_selected)
            self._subtitle_vars[code] = var

        for entry in subs["auto"]:
            code = entry["code"]
            key = f"auto:{code}"
            pre_selected = code in default_langs or "all" in default_langs
            var = ctk.BooleanVar(value=pre_selected)
            self._subtitle_vars[key] = var

        self._subtitle_select_all_var.set(False)
        self._update_subtitle_summary()
        self._subtitle_summary_frame.grid(
            row=5, column=0, columnspan=4, padx=12, pady=(0, 6), sticky="ew",
        )

    def _hide_subtitle_picker(self) -> None:
        self._subtitle_summary_frame.grid_forget()
        self._available_subtitles = {"manual": [], "auto": []}
        self._subtitle_vars.clear()
        if self._subtitle_dialog and self._subtitle_dialog.winfo_exists():
            self._subtitle_dialog.destroy()
        self._subtitle_dialog = None

    def _update_subtitle_summary(self) -> None:
        """Update the subtitle summary label with current selection count."""
        total = len(self._subtitle_vars)
        selected = sum(1 for v in self._subtitle_vars.values() if v.get())
        if selected == 0:
            text = t("format.subtitle_summary_none", total=total)
        elif selected == total:
            text = t("format.subtitle_summary_all", total=total)
        else:
            text = t("format.subtitle_summary_some", selected=selected, total=total)
        self._subtitle_summary_label.configure(text=text)

    def _open_subtitle_picker_dialog(self) -> None:
        """Open or focus the non-modal subtitle picker dialog."""
        if self._subtitle_dialog and self._subtitle_dialog.winfo_exists():
            self._subtitle_dialog.focus()
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title(t("format.subtitle_dialog_title"))
        dialog.geometry("400x350")
        dialog.minsize(320, 200)
        dialog.resizable(True, True)
        dialog.transient(self)
        self._subtitle_dialog = dialog

        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        header.grid_columnconfigure(_c(0, 1), weight=1)

        ctk.CTkLabel(
            header, text=t("format.subtitle_languages"),
            font=ctk.CTkFont(size=13, weight="bold"), anchor=_anchor_start(),
        ).grid(row=0, column=_c(0, 1), sticky=_sticky_start())

        select_all_btn = ctk.CTkCheckBox(
            header, text=t("format.select_all"),
            variable=self._subtitle_select_all_var,
            font=ctk.CTkFont(size=11), command=self._on_subtitle_select_all,
        )
        select_all_btn.grid(row=0, column=_c(1, 1), padx=_pad_end(0, 8))

        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        subs = self._available_subtitles
        row = 0
        if subs["manual"]:
            ctk.CTkLabel(
                scroll, text=t("format.subtitle_manual"),
                font=ctk.CTkFont(size=11, weight="bold"), anchor=_anchor_start(),
            ).grid(row=row, column=0, sticky=_sticky_start(), pady=(2, 2))
            row += 1
            for entry in subs["manual"]:
                code = entry["code"]
                name = entry["name"]
                var = self._subtitle_vars[code]
                label = f"{name} ({code})" if name != code else code
                ctk.CTkCheckBox(
                    scroll, text=label, variable=var,
                    font=ctk.CTkFont(size=12),
                    command=self._update_subtitle_summary,
                ).grid(row=row, column=0, sticky=_sticky_start(), pady=1)
                row += 1

        if subs["auto"]:
            ctk.CTkLabel(
                scroll, text=t("format.subtitle_auto"),
                font=ctk.CTkFont(size=11, weight="bold"), anchor=_anchor_start(),
            ).grid(row=row, column=0, sticky=_sticky_start(), pady=(6, 2))
            row += 1
            for entry in subs["auto"]:
                code = entry["code"]
                name = entry["name"]
                key = f"auto:{code}"
                var = self._subtitle_vars[key]
                label = f"{name} ({code})" if name != code else code
                ctk.CTkCheckBox(
                    scroll, text=label, variable=var,
                    font=ctk.CTkFont(size=12),
                    command=self._update_subtitle_summary,
                ).grid(row=row, column=0, sticky=_sticky_start(), pady=1)
                row += 1

    def _on_subtitle_select_all(self) -> None:
        select = self._subtitle_select_all_var.get()
        for var in self._subtitle_vars.values():
            var.set(select)
        self._update_subtitle_summary()

    def _get_selected_subtitle_langs(self) -> list[str] | None:
        """Return list of selected subtitle language codes, or None if picker not used."""
        if not self._subtitle_vars:
            return None
        selected = []
        for key, var in self._subtitle_vars.items():
            if var.get():
                code = key.replace("auto:", "")
                if code not in selected:
                    selected.append(code)
        return selected if selected else None

    # ------------------------------------------------- Chapter picker
    def _populate_chapter_picker(self, info: dict) -> None:
        """Parse chapters from info_dict and show summary row."""
        chapters = parse_chapters(info)
        self._available_chapters = chapters
        self._chapter_vars.clear()

        if not chapters:
            self._chapter_summary_frame.grid_forget()
            return

        for _ch in chapters:
            var = ctk.BooleanVar(value=True)
            self._chapter_vars.append(var)

        self._chapter_select_all_var.set(True)
        self._update_chapter_summary()
        self._chapter_summary_frame.grid(
            row=6, column=0, columnspan=4, padx=12, pady=(0, 6), sticky="ew",
        )

    def _hide_chapter_picker(self) -> None:
        self._chapter_summary_frame.grid_forget()
        self._available_chapters = []
        self._chapter_vars.clear()
        if self._chapter_dialog and self._chapter_dialog.winfo_exists():
            self._chapter_dialog.destroy()
        self._chapter_dialog = None

    def _update_chapter_summary(self) -> None:
        """Update the chapter summary label with current selection count."""
        total = len(self._chapter_vars)
        selected = sum(1 for v in self._chapter_vars if v.get())
        if selected == total:
            text = t("format.chapter_summary_all", total=total)
        elif selected == 0:
            text = t("format.chapter_summary_none", total=total)
        else:
            text = t("format.chapter_summary_some", selected=selected, total=total)
        self._chapter_summary_label.configure(text=text)

    def _open_chapter_picker_dialog(self) -> None:
        """Open or focus the non-modal chapter picker dialog."""
        if self._chapter_dialog and self._chapter_dialog.winfo_exists():
            self._chapter_dialog.focus()
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title(t("format.chapter_dialog_title"))
        dialog.geometry("400x350")
        dialog.minsize(320, 200)
        dialog.resizable(True, True)
        dialog.transient(self)
        self._chapter_dialog = dialog

        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        header.grid_columnconfigure(_c(0, 1), weight=1)

        ctk.CTkLabel(
            header, text=t("format.chapters"),
            font=ctk.CTkFont(size=13, weight="bold"), anchor=_anchor_start(),
        ).grid(row=0, column=_c(0, 1), sticky=_sticky_start())

        select_all_btn = ctk.CTkCheckBox(
            header, text=t("format.select_all"),
            variable=self._chapter_select_all_var,
            font=ctk.CTkFont(size=11), command=self._on_chapter_select_all,
        )
        select_all_btn.grid(row=0, column=_c(1, 1), padx=_pad_end(0, 8))

        scroll = ctk.CTkScrollableFrame(dialog)
        scroll.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        for i, ch in enumerate(self._available_chapters):
            var = self._chapter_vars[i]
            time_range = format_chapter_range(ch["start_time"], ch["end_time"])
            label = f"{i + 1}. {ch['title']} ({time_range})"
            ctk.CTkCheckBox(
                scroll, text=label, variable=var,
                font=ctk.CTkFont(size=12),
                command=self._update_chapter_summary,
            ).grid(row=i, column=0, sticky=_sticky_start(), pady=1)

    def _on_chapter_select_all(self) -> None:
        select = self._chapter_select_all_var.get()
        for var in self._chapter_vars:
            var.set(select)
        self._update_chapter_summary()

    def _get_selected_chapters(self) -> list[str] | None:
        """Return list of selected chapter titles, or None if all selected or picker not used."""
        if not self._chapter_vars or not self._available_chapters:
            return None
        selected = []
        all_selected = True
        for i, var in enumerate(self._chapter_vars):
            if var.get():
                selected.append(self._available_chapters[i]["title"])
            else:
                all_selected = False
        if all_selected:
            return None
        return selected if selected else None

    # --------------------------------------------------- Download section UI
    def _on_section_toggled(self) -> None:
        if self._section_var.get():
            self._section_frame.grid(row=1, column=0, columnspan=4, pady=(6, 0), sticky="ew")
            self._section_error_label.configure(text="")
        else:
            self._section_frame.grid_forget()
            self._section_error_label.configure(text="")

    def _update_section_visibility(self) -> None:
        """Show section controls only in single mode."""
        if self._input_mode == "single":
            self._section_checkbox.grid(row=0, column=1, padx=(0, 8))
            if self._section_var.get():
                self._section_frame.grid(row=1, column=0, columnspan=4, pady=(6, 0), sticky="ew")
        else:
            self._section_checkbox.grid_forget()
            self._section_frame.grid_forget()
            self._section_var.set(False)

    def _validate_section(self) -> bool:
        """Check section timestamps and show an error if invalid. Returns True if OK."""
        if not self._section_var.get():
            return True
        start = self._section_start_entry.get().strip()
        end = self._section_end_entry.get().strip()

        if not start and not end:
            self._section_error_label.configure(text=t("section.error_enter_time"))
            return False

        if start and parse_timestamp(start) is None:
            self._section_error_label.configure(text=t("section.error_invalid_start"))
            return False
        if end and parse_timestamp(end) is None:
            self._section_error_label.configure(text=t("section.error_invalid_end"))
            return False

        err = validate_time_range(start, end)
        if err:
            self._section_error_label.configure(text=err)
            return False

        self._section_error_label.configure(text="")
        return True

    # ------------------------------------------------------- Clipboard monitor
    def _start_clipboard_monitor(self) -> None:
        if self._clipboard_job is not None:
            return
        try:
            self._clipboard_last = self.clipboard_get()
        except Exception:
            self._clipboard_last = ""
        self._poll_clipboard()

    def _stop_clipboard_monitor(self) -> None:
        if self._clipboard_job is not None:
            self.after_cancel(self._clipboard_job)
            self._clipboard_job = None

    def _poll_clipboard(self) -> None:
        try:
            text = self.clipboard_get().strip()
        except Exception:
            text = ""

        if text and text != self._clipboard_last and is_valid_url(text):
            existing = self._get_urls()
            if text not in existing:
                if self._input_mode == "single":
                    current = self._url_entry.get().strip()
                    if current:
                        self._auto_switch_to_multiple(current + "\n" + text)
                    else:
                        self._url_entry.delete(0, "end")
                        self._url_entry.insert(0, text)
                else:
                    current = self._url_textbox.get("1.0", "end").strip()
                    if current:
                        self._url_textbox.insert("end", "\n" + text)
                    else:
                        self._url_textbox.delete("1.0", "end")
                        self._url_textbox.insert("1.0", text)
                self._log(t("log.clipboard_added", url=text))

        self._clipboard_last = text
        self._clipboard_job = self.after(1000, self._poll_clipboard)

    # --------------------------------------------------------- History panel
    def _toggle_history(self) -> None:
        if self._history_visible:
            self._history_frame.grid_forget()
            self._log_box.grid(row=1, column=0, padx=8, pady=(4, 8), sticky="nsew")
            self._history_toggle_btn.configure(text=t("log.show_history"))
            self._history_visible = False
        else:
            self._populate_history()
            self._log_box.grid_forget()
            self._history_frame.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")
            self._history_toggle_btn.configure(text=t("log.show_log"))
            self._history_visible = True

    def _populate_history(self) -> None:
        self._history_textbox.configure(state="normal")
        self._history_textbox.delete("1.0", "end")

        entries = self._state.history
        if not entries:
            self._history_textbox.insert("1.0", t("history.empty"))
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
                self._history_textbox.insert("end", line + "\n\n")

        self._history_textbox.configure(state="disabled")

    # -------------------------------------------------------- Video preview
    def _on_preview(self) -> None:
        urls = self._get_urls()
        if not urls:
            self._preview_label.configure(text=t("preview.enter_url"), text_color="gray")
            return

        url = urls[0]
        if not is_valid_url(url):
            self._preview_label.configure(text=t("preview.invalid_url"), text_color="#dc3545")
            return

        self._preview_label.configure(text=t("preview.fetching"), text_color="gray")
        self._preview_btn.configure(state="disabled")

        def _on_info(info: dict | None, error: str | None) -> None:
            self._call_on_main(lambda: self._show_preview(info, error))

        self._manager.extract_info(url, _on_info)

    def _show_preview(self, info: dict | None, error: str | None) -> None:
        self._preview_btn.configure(state="normal")
        if error or not info:
            self._preview_label.configure(
                text=t("preview.failed", error=error or "no data"),
                text_color="#dc3545",
            )
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

        self._preview_label.configure(text=" | ".join(parts), text_color="#17a2b8")

        self._last_preview_url_str = "\n".join(self._get_urls())
        self._populate_format_picker(info)
        self._populate_subtitle_picker(info)
        self._populate_chapter_picker(info)

    # -------------------------------------------------------- State helpers

    def _restore_state(self) -> None:
        last = self._state.last_input

        mode = last.get("input_mode", "single")
        if mode not in ("single", "multiple"):
            mode = "single"
        self._switch_mode(mode)

        pview = last.get("progress_view", "simple")
        if pview not in ("simple", "detailed"):
            pview = "simple"
        self._progress_view = pview
        label = t("progress.view_detailed") if pview == "detailed" else t("progress.view_simple")
        self._progress_view_var.set(label)

        if last.get("urls"):
            urls_text = "\n".join(last["urls"])
            if self._input_mode == "single":
                self._url_entry.delete(0, "end")
                self._url_entry.insert(0, last["urls"][0] if last["urls"] else "")
            else:
                self._url_textbox.delete("1.0", "end")
                self._url_textbox.insert("1.0", urls_text)

        if last.get("output_dir"):
            self._output_dir = last["output_dir"]
            self._folder_var.set(self._output_dir)
        if last.get("format"):
            fmt = last["format"]
            if fmt in FORMAT_PRESETS:
                self._format_var.set(fmt)
        if last.get("split_chapters"):
            self._split_chapters_var.set(True)

        if last.get("download_section"):
            self._section_var.set(True)
            self._on_section_toggled()
        if last.get("section_start"):
            self._section_start_entry.delete(0, "end")
            self._section_start_entry.insert(0, last["section_start"])
        if last.get("section_end"):
            self._section_end_entry.delete(0, "end")
            self._section_end_entry.insert(0, last["section_end"])

        if last.get("custom_format_enabled"):
            self._custom_format_var.set(True)
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
            self._rebuild_queue_rows()
            self._log(t("log.restored_queue", count=len(self._queue)))

    def _restore_geometry(self) -> None:
        geo = self._state.window_geometry
        if geo:
            with contextlib.suppress(Exception):
                self.geometry(geo)

    def _on_close(self) -> None:
        if self._manager.is_busy and self._tray.available:
            self.withdraw()
            if not self._tray_notified_minimize:
                self._tray.notify(t("app.title"), t("notify.minimized"))
                self._tray_notified_minimize = True
            return
        try:
            self._shutdown()
        except Exception:
            self.destroy()

    def _on_iconify(self, event: object) -> None:
        """Minimize to tray instead of taskbar when tray is available."""
        if not self._tray.available:
            return
        if event and getattr(event, "widget", None) is self:
            self.withdraw()

    def _poll_tray(self) -> None:
        """Poll tray events from the main thread to avoid cross-thread Tk calls."""
        self._tray.poll_events()
        self.after(250, self._poll_tray)

    def _tray_show(self) -> None:
        self.deiconify()
        self.focus()
        self.lift()

    def _tray_quit(self) -> None:
        self._manager.cancel()
        self._shutdown()

    def _shutdown(self) -> None:
        self._stop_clipboard_monitor()
        with contextlib.suppress(Exception):
            self._state.window_geometry = self.geometry()
        self._persist_queue()
        self._state.save()
        self._tray.stop()
        self.destroy()

    def _on_folder_selected(self, folder: str) -> None:
        self._output_dir = folder

    # ----------------------------------------------------------- Actions

    def _get_urls(self) -> list[str]:
        """Extract non-empty, stripped URLs from the active input widget."""
        if self._input_mode == "single":
            raw = self._url_entry.get().strip()
            return [raw] if raw else []
        raw = self._url_textbox.get("1.0", "end").strip()
        if not raw:
            return []
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def _on_paste(self) -> None:
        try:
            text = self.clipboard_get().strip()
            if not text:
                return
            if self._input_mode == "single" and "\n" in text:
                current = self._url_entry.get().strip()
                combined = (current + "\n" + text) if current else text
                self._auto_switch_to_multiple(combined)
                return
            if self._input_mode == "single":
                current = self._url_entry.get().strip()
                if current:
                    self._auto_switch_to_multiple(current + "\n" + text)
                else:
                    self._url_entry.delete(0, "end")
                    self._url_entry.insert(0, text)
            else:
                current = self._url_textbox.get("1.0", "end").strip()
                if current:
                    self._url_textbox.insert("end", "\n" + text)
                else:
                    self._url_textbox.delete("1.0", "end")
                    self._url_textbox.insert("1.0", text)
        except Exception:
            self._log(t("log.clipboard_error"))

    def _on_browse(self) -> None:
        directory = filedialog.askdirectory(initialdir=self._output_dir)
        if directory:
            self._output_dir = directory
            self._state.add_recent_folder(directory)
            self._folder_var.set(directory)
            self._folder_menu.configure(values=self._state.recent_folders)

    def _on_open_folder(self) -> None:
        open_folder(self._output_dir)

    def _update_playlist_hint(self, urls: list[str]) -> None:
        if not urls:
            self._playlist_label.configure(text="")
            return
        playlist_mode, ambiguous = self._classify_urls(urls)
        if playlist_mode:
            self._playlist_label.configure(text=t("format.playlist_detected"), text_color="#28a745")
        elif ambiguous:
            self._playlist_label.configure(text=t("format.playlist_ambiguous"), text_color="#e0a800")
        else:
            self._playlist_label.configure(text="")

    def _classify_urls(self, urls: list[str]) -> tuple[bool, list[str]]:
        """Determine playlist mode and check for ambiguous URLs."""
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
            self._rebuild_queue_rows()
            self._log(t("log.queued_urls", count=len(urls)))
            return

        self._start_download(urls, playlist=playlist_mode)

    def _build_queue_entry(self, urls: list[str], playlist: bool) -> dict:
        """Build a rich queue entry dict capturing the current download settings."""
        format_key = self._format_var.get()
        download_section = self._section_var.get() and self._input_mode == "single"
        convert_val = self._convert_var.get()
        sub_val = self._subtitle_mode_var.get()
        return {
            "urls": urls,
            "playlist": playlist,
            "format_key": format_key,
            "output_dir": self._output_dir,
            "split_chapters": self._split_chapters_var.get(),
            "custom_format_string": self._get_custom_format_string() if self._custom_format_enabled else "",
            "section_start": self._section_start_entry.get().strip() if download_section else "",
            "section_end": self._section_end_entry.get().strip() if download_section else "",
            "convert_format": "" if convert_val == "None" else convert_val.lower(),
            "subtitle_mode": {"Embed": "embed", "File": "file"}.get(sub_val, ""),
            "subtitle_burn": self._burn_sub_var.get(),
            "selected_chapters": self._get_selected_chapters(),
            "selected_subtitle_langs": self._get_selected_subtitle_langs(),
            "status": "queued",
        }

    def _persist_queue(self) -> None:
        self._state.save_queue(list(self._queue))

    def _update_queue_label(self) -> None:
        count = len(self._queue)
        if count:
            self._queue_label.configure(text=t("queue.label_count", count=count))
        else:
            self._queue_label.configure(text="")

    def _process_queue(self) -> None:
        if self._queue and not self._manager.is_busy:
            entry = self._queue.pop(0)
            self._persist_queue()
            self._update_queue_label()
            self._rebuild_queue_rows()
            self._start_download_from_entry(entry)

    def _show_ambiguous_dialog(self, urls: list[str], ambiguous: list[str]) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title(t("dialog.playlist_title"))
        dialog.geometry("420x150")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        count = len(ambiguous)
        if count == 1:
            body = t("dialog.playlist_single_url")
        else:
            body = t("dialog.playlist_multi_url", count=count)
        ctk.CTkLabel(
            dialog,
            text=body,
            font=ctk.CTkFont(size=13),
            justify="center",
        ).pack(pady=(20, 16))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(0, 12))

        def pick(playlist: bool) -> None:
            dialog.destroy()
            if self._manager.is_busy:
                entry = self._build_queue_entry(urls, playlist)
                self._queue.append(entry)
                self._persist_queue()
                self._update_queue_label()
                self._rebuild_queue_rows()
                self._log(t("log.queued_urls_short", count=len(urls)))
            else:
                self._start_download(urls, playlist=playlist)

        ctk.CTkButton(
            btn_frame, text=t("dialog.single_video_only"), width=160,
            command=lambda: pick(False),
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame, text=t("dialog.entire_playlist"), width=160,
            fg_color="#28a745", hover_color="#218838",
            command=lambda: pick(True),
        ).pack(side="left", padx=8)

    def _start_download(self, urls: list[str], playlist: bool) -> None:
        os.makedirs(self._output_dir, exist_ok=True)

        format_key = self._format_var.get()
        split_chapters = self._split_chapters_var.get()
        download_section = self._section_var.get() and self._input_mode == "single"
        section_start = self._section_start_entry.get().strip() if download_section else ""
        section_end = self._section_end_entry.get().strip() if download_section else ""

        custom_format_str = ""
        video_format_id = ""
        audio_format_id = ""
        if self._custom_format_enabled:
            custom_format_str = self._get_custom_format_string()
            video_label = self._video_format_var.get()
            audio_label = self._audio_format_var.get()
            for f in self._available_video_formats:
                if f["label"] == video_label:
                    video_format_id = f["format_id"]
                    break
            for f in self._available_audio_formats:
                if f["label"] == audio_label:
                    audio_format_id = f["format_id"]
                    break

        self._is_playlist_download = playlist
        self._is_audio_download = format_key == "Audio Only (mp3)" and not self._custom_format_enabled
        self._accumulated_bytes = 0
        self._current_urls = urls
        self._concurrent_mode = False

        self._state.save_last_input(
            urls, self._output_dir, format_key, split_chapters,
            input_mode=self._input_mode, progress_view=self._progress_view,
            download_section=download_section,
            section_start=section_start, section_end=section_end,
            custom_format_enabled=self._custom_format_enabled,
            video_format_id=video_format_id,
            audio_format_id=audio_format_id,
        )
        self._state.add_recent_folder(self._output_dir)

        self._init_download_items(urls)
        self._folder_menu.configure(values=self._state.recent_folders)

        mode = t("log.download_mode_playlist") if playlist else t("log.download_mode_video")
        section_info = ""
        if download_section:
            s = section_start or "0:00"
            e = section_end or "end"
            section_info = t("log.section_info", start=s, end=e)
        format_display = custom_format_str if self._custom_format_enabled else format_key

        pp_parts: list[str] = []
        convert_val = self._convert_var.get()
        if convert_val != "None":
            pp_parts.append(t("log.pp_convert", fmt=convert_val))
        sub_val = self._subtitle_mode_var.get()
        if sub_val != "None":
            pp_parts.append(t("log.pp_embed_subs") if sub_val == "Embed" else t("log.pp_subs_file"))
        if self._burn_sub_var.get():
            pp_parts.append(t("log.pp_burn_subs"))
        pp_info = f" [{', '.join(pp_parts)}]" if pp_parts else ""

        self._log(t("log.starting_download", count=len(urls), mode=mode, section=section_info, format=format_display, pp=pp_info))
        self._tray.update_tooltip(t("notify.downloading", done=0, total=len(urls)))
        self._progress_bar.set(0)
        self._download_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._open_folder_btn.configure(state="disabled")

        max_concurrent = int(self._state.settings.get("max_concurrent_downloads", 3))
        use_concurrent = max_concurrent > 1 and len(urls) > 1

        def on_item_done(index: int, total: int, error: str | None) -> None:
            self._call_on_main(lambda: self._item_finished(index, total, error))

        def on_done(error: str | None) -> None:
            self._call_on_main(lambda: self._download_finished(error))

        selected_chapters = self._get_selected_chapters()
        selected_subtitle_langs = self._get_selected_subtitle_langs()

        common_kwargs: dict = dict(
            split_chapters=split_chapters,
            playlist=playlist,
            item_done_callback=on_item_done,
            done_callback=on_done,
            settings=self._state.settings,
            section_start=section_start,
            section_end=section_end,
            format_string=custom_format_str,
            selected_chapters=selected_chapters,
            selected_subtitle_langs=selected_subtitle_langs,
        )

        if use_concurrent:
            self._concurrent_mode = True

            def on_progress_concurrent(item_index: int, data: dict) -> None:
                self._call_on_main(lambda idx=item_index, d=data: self._update_progress_concurrent(idx, d))

            self._manager.download_batch_concurrent(
                urls, format_key, self._output_dir,
                max_workers=max_concurrent,
                progress_callback=on_progress_concurrent,
                **common_kwargs,
            )
        else:
            def on_progress(data: dict) -> None:
                self._call_on_main(lambda d=data: self._update_progress(d))

            self._manager.download_batch(
                urls, format_key, self._output_dir,
                progress_callback=on_progress,
                **common_kwargs,
            )

    def _start_download_from_entry(self, entry: dict) -> None:
        """Start a download from a persisted queue entry dict."""
        urls = entry["urls"]
        playlist = entry.get("playlist", False)
        format_key = entry.get("format_key", "Best (video+audio)")
        output_dir = entry.get("output_dir", self._output_dir)
        split_chapters = entry.get("split_chapters", False)
        custom_format_str = entry.get("custom_format_string", "")
        section_start = entry.get("section_start", "")
        section_end = entry.get("section_end", "")
        selected_chapters = entry.get("selected_chapters") or None
        selected_subtitle_langs = entry.get("selected_subtitle_langs") or None

        if "convert_format" in entry:
            self._state.save_settings(
                convert_format=entry.get("convert_format", ""),
                subtitle_mode=entry.get("subtitle_mode", ""),
                subtitle_burn=entry.get("subtitle_burn", False),
            )

        os.makedirs(output_dir, exist_ok=True)

        self._is_playlist_download = playlist
        self._is_audio_download = format_key == "Audio Only (mp3)" and not custom_format_str
        self._accumulated_bytes = 0
        self._current_urls = urls
        self._concurrent_mode = False
        self._output_dir = output_dir

        self._init_download_items(urls)

        mode = t("log.download_mode_playlist") if playlist else t("log.download_mode_video")
        self._log(t("log.starting_queued", count=len(urls), mode=mode, format=format_key))
        self._progress_bar.set(0)
        self._download_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")
        self._open_folder_btn.configure(state="disabled")

        max_concurrent = int(self._state.settings.get("max_concurrent_downloads", 3))
        use_concurrent = max_concurrent > 1 and len(urls) > 1

        def on_item_done(index: int, total: int, error: str | None) -> None:
            self._call_on_main(lambda: self._item_finished(index, total, error))

        def on_done(error: str | None) -> None:
            self._call_on_main(lambda: self._download_finished(error))

        common_kwargs: dict = dict(
            split_chapters=split_chapters,
            playlist=playlist,
            item_done_callback=on_item_done,
            done_callback=on_done,
            settings=self._state.settings,
            section_start=section_start,
            section_end=section_end,
            format_string=custom_format_str,
            selected_chapters=selected_chapters,
            selected_subtitle_langs=selected_subtitle_langs,
        )

        if use_concurrent:
            self._concurrent_mode = True

            def on_progress_concurrent(item_index: int, data: dict) -> None:
                self._call_on_main(lambda idx=item_index, d=data: self._update_progress_concurrent(idx, d))

            self._manager.download_batch_concurrent(
                urls, format_key, output_dir,
                max_workers=max_concurrent,
                progress_callback=on_progress_concurrent,
                **common_kwargs,
            )
        else:
            def on_progress(data: dict) -> None:
                self._call_on_main(lambda d=data: self._update_progress(d))

            self._manager.download_batch(
                urls, format_key, output_dir,
                progress_callback=on_progress,
                **common_kwargs,
            )

    def _on_cancel(self) -> None:
        self._manager.cancel()
        self._queue.clear()
        self._persist_queue()
        self._update_queue_label()
        self._rebuild_queue_rows()
        self._log(t("log.cancelling"))

    # ---------------------------------------------------------- Callbacks

    def _update_progress(self, data: dict) -> None:
        """Progress callback for sequential (non-concurrent) downloads."""
        title = data.get("title")
        if title and title != self._video_title:
            self._video_title = title
            duration = data.get("duration")
            dur_str = ""
            if duration:
                m, s = divmod(int(duration), 60)
                dur_str = f" [{m}:{s:02d}]"
            self._title_label.configure(text=f"{truncate_filename(title, 60)}{dur_str}")

        total = data["total_bytes"]
        downloaded = data["downloaded_bytes"]

        if total and total > 0:
            fraction = downloaded / total
            self._progress_bar.set(fraction)
            pct = f"{fraction * 100:.1f}%"
        else:
            fraction = 0
            pct = format_bytes(downloaded)

        speed = format_speed(data["speed"])
        eta = format_eta(data["eta"])
        self._progress_detail.configure(text=t("progress.detail", pct=pct, speed=speed, eta=eta))

        if data["status"] == "finished":
            self._accumulated_bytes += data["total_bytes"] or data["downloaded_bytes"]
            self._progress_bar.set(1)
            self._progress_detail.configure(text=t("progress.processing"))
            fraction = 1.0

        idx = self._current_item_index
        if idx < len(self._download_items):
            item = self._download_items[idx]
            item["status"] = "downloading"
            item["progress"] = fraction
            if title:
                item["title"] = title
            if data["status"] == "finished":
                item["progress"] = 1.0
                item["accumulated_bytes"] = self._accumulated_bytes
            if self._progress_view == "detailed":
                self._update_detail_row(idx)

    def _update_progress_concurrent(self, item_index: int, data: dict) -> None:
        """Progress callback for concurrent downloads -- routes by item index."""
        if item_index >= len(self._download_items):
            return

        item = self._download_items[item_index]
        title = data.get("title")
        if title:
            item["title"] = title

        total_bytes = data["total_bytes"]
        downloaded = data["downloaded_bytes"]

        if total_bytes and total_bytes > 0:
            fraction = downloaded / total_bytes
        else:
            fraction = 0.0

        item["status"] = "downloading"
        item["progress"] = fraction

        if data["status"] == "finished":
            item["progress"] = 1.0
            item["accumulated_bytes"] += data["total_bytes"] or data["downloaded_bytes"]

        if self._progress_view == "detailed":
            self._update_detail_row(item_index)

        self._update_aggregate_progress(data)

    def _update_aggregate_progress(self, latest_data: dict) -> None:
        """Update the simple progress bar/label with aggregate info across all items."""
        if not self._download_items:
            return

        total_progress = sum(it["progress"] for it in self._download_items)
        aggregate = total_progress / len(self._download_items)
        self._progress_bar.set(aggregate)

        active = [it for it in self._download_items if it["status"] == "downloading"]
        if active:
            latest_title = active[-1].get("title", "")
            if latest_title:
                self._video_title = latest_title

        title = latest_data.get("title")
        if title and title != self._video_title:
            self._video_title = title
        if self._video_title:
            duration = latest_data.get("duration")
            dur_str = ""
            if duration:
                m, s = divmod(int(duration), 60)
                dur_str = f" [{m}:{s:02d}]"
            self._title_label.configure(text=f"{truncate_filename(self._video_title, 60)}{dur_str}")

        pct = f"{aggregate * 100:.1f}%"
        speed = format_speed(latest_data.get("speed", 0))
        eta = format_eta(latest_data.get("eta", 0))
        self._progress_detail.configure(text=t("progress.detail", pct=pct, speed=speed, eta=eta))

    def _item_finished(self, index: int, total: int, error: str | None) -> None:
        """Called when a single URL completes (index is 1-based from manager)."""
        url = self._current_urls[index - 1] if index <= len(self._current_urls) else ""
        item_idx = index - 1

        if item_idx < len(self._download_items):
            item = self._download_items[item_idx]
            if error:
                item["status"] = "failed"
                item["error"] = error
            else:
                item["status"] = "done"
                item["progress"] = 1.0
            if self._progress_view == "detailed":
                self._update_detail_row(item_idx)

        if not self._concurrent_mode:
            self._current_item_index = index

        if self._input_mode == "multiple":
            done_count = sum(1 for it in self._download_items if it["status"] in ("done", "failed"))
            self._overall_label.configure(text=t("progress.overall", done=done_count, total=self._total_items))
            self._tray.update_tooltip(t("notify.downloading", done=done_count, total=self._total_items))

        item_title = ""
        if item_idx < len(self._download_items):
            item_title = self._download_items[item_idx].get("title", "")

        if error:
            self._log(t("log.item_error", index=index, total=total, error=error))
            self._state.record_failed(title=item_title or self._video_title, url=url)
        else:
            self._log(t("log.item_done", index=index, total=total))
            if self._concurrent_mode:
                bytes_dl = self._download_items[item_idx]["accumulated_bytes"] if item_idx < len(self._download_items) else 0
            else:
                bytes_dl = self._accumulated_bytes
            self._state.record_download(
                bytes_downloaded=bytes_dl,
                is_audio=self._is_audio_download,
                is_playlist=self._is_playlist_download,
                title=item_title or self._video_title,
                url=url,
            )
            if not self._concurrent_mode:
                self._accumulated_bytes = 0
            self._refresh_status_bar()

    def _download_finished(self, error: str | None) -> None:
        self._download_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")
        self._open_folder_btn.configure(state="normal")
        if error:
            self._log(t("log.error", error=error))
            send_notification(t("app.title"), t("notify.download_failed", error=error))
        else:
            self._progress_bar.set(1)
            self._progress_detail.configure(text=t("progress.done"))
            self._log(t("log.all_complete", dir=self._output_dir))
            send_notification(t("app.title"), t("notify.all_complete"))

            if self._input_mode == "multiple" and self._total_items > 0:
                self._overall_label.configure(text=t("progress.overall", done=self._total_items, total=self._total_items))

        self._tray.update_tooltip(t("tray.tooltip"))
        self._refresh_status_bar()

        self.after(100, self._process_queue)

    # ------------------------------------------------------------ Helpers

    def _log(self, message: str) -> None:
        self._log_box.configure(state="normal")
        self._log_box.insert("end", message + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")
