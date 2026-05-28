import contextlib
from collections.abc import Callable
from tkinter import filedialog
from typing import Any

import customtkinter as ctk

from i18n import get_available_languages, is_rtl, t
from state import AppState

_BROWSERS = ["", "chrome", "firefox", "edge", "safari", "brave", "opera", "vivaldi"]
_BROWSER_LABELS = ["None", "Chrome", "Firefox", "Edge", "Safari", "Brave", "Opera", "Vivaldi"]

_THEMES = ["system", "dark", "light"]
_THEME_LABELS = ["System", "Dark", "Light"]



class SettingsWindow(ctk.CTkToplevel):
    def __init__(
        self,
        parent: ctk.CTk,
        state: AppState,
        on_theme_changed: Callable[[], None] | None = None,
        on_clipboard_changed: Callable[[bool], None] | None = None,
        on_language_changed: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(t("settings.title"))
        self.geometry("480x640")
        self.minsize(420, 540)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self._state = state
        self._on_theme_changed = on_theme_changed
        self._on_clipboard_changed = on_clipboard_changed
        self._on_language_changed = on_language_changed
        self._settings: dict[str, Any] = dict(state.settings)

        self._build_ui()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self)
        scroll.grid(row=0, column=0, padx=12, pady=12, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        self._scroll = scroll

        row = 0
        row = self._build_appearance_section(scroll, row)
        row = self._build_download_section(scroll, row)
        row = self._build_network_section(scroll, row)
        self._build_advanced_section(scroll, row)

        self._bind_mousewheel(scroll)

    # ----------------------------------------------------------- Appearance

    def _build_appearance_section(self, parent: ctk.CTkFrame, start_row: int) -> int:
        row = start_row
        s = "e" if is_rtl() else "w"

        ctk.CTkLabel(parent, text=t("settings.appearance"), font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=row, column=0, sticky=s, pady=(8, 12)
        )
        row += 1

        # Theme
        ctk.CTkLabel(parent, text=t("settings.theme"), font=ctk.CTkFont(size=13)).grid(
            row=row, column=0, sticky=s, pady=(0, 4)
        )
        row += 1

        theme_labels = [t("settings.theme_system"), t("settings.theme_dark"), t("settings.theme_light")]
        current_theme = self._settings.get("theme", "system")
        theme_idx = _THEMES.index(current_theme) if current_theme in _THEMES else 0
        self._theme_var = ctk.StringVar(value=theme_labels[theme_idx])
        theme_menu = ctk.CTkSegmentedButton(
            parent, values=theme_labels, variable=self._theme_var,
            command=self._on_theme_change,
        )
        theme_menu.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        row += 1

        # Language
        ctk.CTkLabel(parent, text=t("settings.language"), font=ctk.CTkFont(size=13)).grid(
            row=row, column=0, sticky=s, pady=(0, 4)
        )
        row += 1

        available_langs = get_available_languages()
        self._lang_codes = [code for code, _ in available_langs]
        lang_labels = [name for _, name in available_langs]
        current_lang = self._settings.get("language", "en")
        current_lang_idx = self._lang_codes.index(current_lang) if current_lang in self._lang_codes else 0
        self._lang_var = ctk.StringVar(value=lang_labels[current_lang_idx])
        lang_menu = ctk.CTkOptionMenu(
            parent, variable=self._lang_var, values=lang_labels,
            command=self._on_language_change,
        )
        lang_menu.grid(row=row, column=0, sticky=s, pady=(0, 12))
        row += 1

        # UI Scale
        ctk.CTkLabel(parent, text=t("settings.ui_scale"), font=ctk.CTkFont(size=13)).grid(
            row=row, column=0, sticky=s, pady=(0, 4)
        )
        row += 1

        scale_frame = ctk.CTkFrame(parent, fg_color="transparent")
        scale_frame.grid(row=row, column=0, sticky="ew", pady=(0, 16))
        scale_frame.grid_columnconfigure(0, weight=1)

        current_scale = self._settings.get("ui_scale", 1.0)
        self._scale_var = ctk.DoubleVar(value=current_scale)
        self._scale_label = ctk.CTkLabel(
            scale_frame, text=f"{int(current_scale * 100)}%", font=ctk.CTkFont(size=12),
            width=45,
        )
        self._scale_label.grid(row=0, column=1, padx=(8, 0))

        scale_slider = ctk.CTkSlider(
            scale_frame, from_=0.8, to=1.5, number_of_steps=14,
            variable=self._scale_var, command=self._on_scale_change,
        )
        scale_slider.grid(row=0, column=0, sticky="ew")
        row += 1

        sep = ctk.CTkFrame(parent, height=2, fg_color="gray70")
        sep.grid(row=row, column=0, sticky="ew", pady=8)
        row += 1

        return row

    # -------------------------------------------------------- Download Defaults

    def _build_download_section(self, parent: ctk.CTkFrame, start_row: int) -> int:
        row = start_row
        s = "e" if is_rtl() else "w"

        ctk.CTkLabel(parent, text=t("settings.download_defaults"), font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=row, column=0, sticky=s, pady=(8, 12)
        )
        row += 1

        # Speed limit
        ctk.CTkLabel(parent, text=t("settings.speed_limit"), font=ctk.CTkFont(size=13)).grid(
            row=row, column=0, sticky=s, pady=(0, 4)
        )
        row += 1

        self._speed_entry = ctk.CTkEntry(parent, placeholder_text=t("settings.speed_limit_placeholder"))
        current_speed = self._settings.get("speed_limit", "")
        if current_speed:
            self._speed_entry.insert(0, current_speed)
        self._speed_entry.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        self._speed_entry.bind("<FocusOut>", lambda _: self._save_text_field("speed_limit", self._speed_entry))
        self._speed_entry.bind("<Return>", lambda _: self._save_text_field("speed_limit", self._speed_entry))
        row += 1

        # Simultaneous downloads
        ctk.CTkLabel(parent, text=t("settings.simultaneous"), font=ctk.CTkFont(size=13)).grid(
            row=row, column=0, sticky=s, pady=(0, 4)
        )
        row += 1

        concurrency_frame = ctk.CTkFrame(parent, fg_color="transparent")
        concurrency_frame.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        concurrency_frame.grid_columnconfigure(0, weight=1)

        current_concurrency = int(self._settings.get("max_concurrent_downloads", 3))
        self._concurrency_var = ctk.IntVar(value=current_concurrency)
        self._concurrency_label = ctk.CTkLabel(
            concurrency_frame, text=str(current_concurrency), font=ctk.CTkFont(size=12),
            width=30,
        )
        self._concurrency_label.grid(row=0, column=1, padx=(8, 0))

        concurrency_slider = ctk.CTkSlider(
            concurrency_frame, from_=1, to=5, number_of_steps=4,
            variable=self._concurrency_var, command=self._on_concurrency_change,
        )
        concurrency_slider.grid(row=0, column=0, sticky="ew")
        row += 1

        # Embed thumbnail
        self._embed_thumb_var = ctk.BooleanVar(value=self._settings.get("embed_thumbnail", False))
        ctk.CTkCheckBox(
            parent, text=t("settings.embed_thumbnail"),
            variable=self._embed_thumb_var, font=ctk.CTkFont(size=13),
            command=lambda: self._save_bool("embed_thumbnail", self._embed_thumb_var),
        ).grid(row=row, column=0, sticky=s, pady=(0, 6))
        row += 1

        # Embed metadata
        self._embed_meta_var = ctk.BooleanVar(value=self._settings.get("embed_metadata", False))
        ctk.CTkCheckBox(
            parent, text=t("settings.embed_metadata"),
            variable=self._embed_meta_var, font=ctk.CTkFont(size=13),
            command=lambda: self._save_bool("embed_metadata", self._embed_meta_var),
        ).grid(row=row, column=0, sticky=s, pady=(0, 6))
        row += 1

        # Subtitle languages
        ctk.CTkLabel(parent, text=t("settings.subtitle_languages"), font=ctk.CTkFont(size=13)).grid(
            row=row, column=0, sticky=s, pady=(6, 4)
        )
        row += 1

        self._subtitle_lang_entry = ctk.CTkEntry(parent, placeholder_text=t("settings.subtitle_languages_placeholder"))
        current_langs = self._settings.get("subtitle_languages", "en")
        if current_langs:
            self._subtitle_lang_entry.insert(0, current_langs)
        self._subtitle_lang_entry.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        self._subtitle_lang_entry.bind("<FocusOut>", lambda _: self._save_text_field("subtitle_languages", self._subtitle_lang_entry))
        self._subtitle_lang_entry.bind("<Return>", lambda _: self._save_text_field("subtitle_languages", self._subtitle_lang_entry))
        row += 1

        # Clipboard monitoring
        self._clip_var = ctk.BooleanVar(value=self._settings.get("clipboard_monitor", False))
        ctk.CTkCheckBox(
            parent, text=t("settings.clipboard_monitor"),
            variable=self._clip_var, font=ctk.CTkFont(size=13),
            command=self._on_clipboard_toggle,
        ).grid(row=row, column=0, sticky=s, pady=(0, 16))
        row += 1

        sep = ctk.CTkFrame(parent, height=2, fg_color="gray70")
        sep.grid(row=row, column=0, sticky="ew", pady=8)
        row += 1

        return row

    # ------------------------------------------------------------- Network

    def _build_network_section(self, parent: ctk.CTkFrame, start_row: int) -> int:
        row = start_row
        s = "e" if is_rtl() else "w"

        ctk.CTkLabel(parent, text=t("settings.network"), font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=row, column=0, sticky=s, pady=(8, 12)
        )
        row += 1

        # Proxy
        ctk.CTkLabel(parent, text=t("settings.proxy"), font=ctk.CTkFont(size=13)).grid(
            row=row, column=0, sticky=s, pady=(0, 4)
        )
        row += 1

        self._proxy_entry = ctk.CTkEntry(parent, placeholder_text=t("settings.proxy_placeholder"))
        current_proxy = self._settings.get("proxy", "")
        if current_proxy:
            self._proxy_entry.insert(0, current_proxy)
        self._proxy_entry.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        self._proxy_entry.bind("<FocusOut>", lambda _: self._save_text_field("proxy", self._proxy_entry))
        self._proxy_entry.bind("<Return>", lambda _: self._save_text_field("proxy", self._proxy_entry))
        row += 1

        # Browser cookies
        ctk.CTkLabel(parent, text=t("settings.browser_cookies"), font=ctk.CTkFont(size=13)).grid(
            row=row, column=0, sticky=s, pady=(0, 4)
        )
        row += 1

        current_browser = self._settings.get("browser_cookies", "")
        browser_idx = _BROWSERS.index(current_browser) if current_browser in _BROWSERS else 0
        self._browser_var = ctk.StringVar(value=_BROWSER_LABELS[browser_idx])
        browser_menu = ctk.CTkOptionMenu(
            parent, variable=self._browser_var, values=_BROWSER_LABELS,
            command=self._on_browser_change,
        )
        browser_menu.grid(row=row, column=0, sticky=s, pady=(0, 2))
        row += 1

        ctk.CTkLabel(
            parent,
            text=t("settings.browser_cookies_help"),
            font=ctk.CTkFont(size=11), text_color="gray", justify="right" if is_rtl() else "left",
        ).grid(row=row, column=0, sticky=s, pady=(0, 12))
        row += 1

        # Cookie file
        ctk.CTkLabel(parent, text=t("settings.cookie_file"), font=ctk.CTkFont(size=13)).grid(
            row=row, column=0, sticky=s, pady=(0, 4)
        )
        row += 1

        cookie_frame = ctk.CTkFrame(parent, fg_color="transparent")
        cookie_frame.grid(row=row, column=0, sticky="ew", pady=(0, 2))
        cookie_frame.grid_columnconfigure(0, weight=1)

        self._cookie_entry = ctk.CTkEntry(cookie_frame, placeholder_text=t("settings.cookie_file_placeholder"))
        current_cookie = self._settings.get("cookie_file", "")
        if current_cookie:
            self._cookie_entry.insert(0, current_cookie)
        self._cookie_entry.grid(row=0, column=0, sticky="ew")
        self._cookie_entry.bind("<FocusOut>", lambda _: self._save_text_field("cookie_file", self._cookie_entry))

        ctk.CTkButton(
            cookie_frame, text=t("settings.cookie_file_browse"), width=80,
            command=self._browse_cookie_file,
        ).grid(row=0, column=1, padx=(6, 0))
        row += 1

        ctk.CTkLabel(
            parent,
            text=t("settings.cookie_file_help"),
            font=ctk.CTkFont(size=11), text_color="gray", justify="right" if is_rtl() else "left",
        ).grid(row=row, column=0, sticky=s, pady=(0, 16))
        row += 1

        sep = ctk.CTkFrame(parent, height=2, fg_color="gray70")
        sep.grid(row=row, column=0, sticky="ew", pady=8)
        row += 1

        return row

    # ------------------------------------------------------------ Advanced

    def _build_advanced_section(self, parent: ctk.CTkFrame, start_row: int) -> int:
        row = start_row
        s = "e" if is_rtl() else "w"

        ctk.CTkLabel(parent, text=t("settings.advanced"), font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=row, column=0, sticky=s, pady=(8, 12)
        )
        row += 1

        self._portable_var = ctk.BooleanVar(value=self._settings.get("portable_mode", False))
        ctk.CTkCheckBox(
            parent, text=t("settings.portable_mode"),
            variable=self._portable_var, font=ctk.CTkFont(size=13),
            command=self._on_portable_toggle,
        ).grid(row=row, column=0, sticky=s, pady=(0, 6))
        row += 1

        ctk.CTkLabel(
            parent,
            text=t("settings.portable_help"),
            font=ctk.CTkFont(size=11), text_color="gray",
        ).grid(row=row, column=0, sticky=s, pady=(0, 16))
        row += 1

        return row

    # ----------------------------------------------------------- Callbacks

    def _on_theme_change(self, label: str) -> None:
        theme_labels = [t("settings.theme_system"), t("settings.theme_dark"), t("settings.theme_light")]
        idx = theme_labels.index(label) if label in theme_labels else 0
        theme = _THEMES[idx]
        ctk.set_appearance_mode(theme)
        self._state.save_settings(theme=theme)
        if self._on_theme_changed:
            self._on_theme_changed()

    def _on_scale_change(self, value: float) -> None:
        value = round(value, 2)
        ctk.set_widget_scaling(value)
        self._scale_label.configure(text=f"{int(value * 100)}%")
        self._state.save_settings(ui_scale=value)

    def _on_concurrency_change(self, value: float) -> None:
        n = max(1, min(5, round(value)))
        self._concurrency_label.configure(text=str(n))
        self._state.save_settings(max_concurrent_downloads=n)

    def _on_clipboard_toggle(self) -> None:
        enabled = self._clip_var.get()
        self._state.save_settings(clipboard_monitor=enabled)
        if self._on_clipboard_changed:
            self._on_clipboard_changed(enabled)

    def _on_browser_change(self, label: str) -> None:
        idx = _BROWSER_LABELS.index(label) if label in _BROWSER_LABELS else 0
        browser = _BROWSERS[idx]
        self._state.save_settings(browser_cookies=browser)

    def _on_language_change(self, label: str) -> None:
        available = get_available_languages()
        lang_names = [name for _, name in available]
        idx = lang_names.index(label) if label in lang_names else 0
        code = available[idx][0]
        self._state.save_settings(language=code)
        if self._on_language_changed:
            self.destroy()
            self._on_language_changed(code)

    def _on_portable_toggle(self) -> None:
        enabled = self._portable_var.get()
        if enabled:
            self._state.enable_portable_mode()
        else:
            self._state.disable_portable_mode()

    def _browse_cookie_file(self) -> None:
        path = filedialog.askopenfilename(
            title=t("settings.cookie_file_dialog_title"),
            filetypes=[(t("settings.cookie_file_dialog_text"), "*.txt"), (t("settings.cookie_file_dialog_all"), "*.*")],
        )
        if path:
            self._cookie_entry.delete(0, "end")
            self._cookie_entry.insert(0, path)
            self._state.save_settings(cookie_file=path)

    def _save_text_field(self, key: str, entry: ctk.CTkEntry) -> None:
        self._state.save_settings(**{key: entry.get().strip()})

    def _save_bool(self, key: str, var: ctk.BooleanVar) -> None:
        self._state.save_settings(**{key: var.get()})

    # -------------------------------------------------------- Scroll fix
    def _bind_mousewheel(self, scroll_frame: ctk.CTkScrollableFrame) -> None:
        """Propagate mousewheel events from all children to the scrollable frame.

        On macOS, child widgets swallow scroll events, preventing the parent
        CTkScrollableFrame from scrolling when the pointer is over them.
        """
        canvas = scroll_frame._parent_canvas
        binding_in_progress = False

        def _on_mousewheel(event: "Any") -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_recursive(widget: "Any") -> None:
            with contextlib.suppress(NotImplementedError, AttributeError):
                widget.bind("<MouseWheel>", _on_mousewheel, add="+")
            try:
                children = widget.winfo_children()
            except Exception:
                return
            for child in children:
                _bind_recursive(child)

        def _on_map(_event: "Any") -> None:
            nonlocal binding_in_progress
            if binding_in_progress:
                return
            binding_in_progress = True
            try:
                _bind_recursive(scroll_frame)
            finally:
                binding_in_progress = False

        _bind_recursive(scroll_frame)
        scroll_frame.bind("<Map>", _on_map, add="+")
