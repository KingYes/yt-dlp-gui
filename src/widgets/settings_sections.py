"""Builder functions for SettingsWindow sections."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from ..i18n import get_available_languages, is_rtl, t

if TYPE_CHECKING:
    from ..settings_window import SettingsWindow

_BROWSERS = ["", "chrome", "firefox", "edge", "safari", "brave", "opera", "vivaldi"]
_BROWSER_LABELS = ["None", "Chrome", "Firefox", "Edge", "Safari", "Brave", "Opera", "Vivaldi"]

_THEMES = ["system", "dark", "light"]
_THEME_LABELS = ["System", "Dark", "Light"]


def build_appearance_section(win: SettingsWindow, parent: ctk.CTkFrame, start_row: int) -> int:
    row = start_row
    s = "e" if is_rtl() else "w"

    ctk.CTkLabel(parent, text=t("settings.appearance"), font=ctk.CTkFont(size=16, weight="bold")).grid(
        row=row, column=0, sticky=s, pady=(8, 12)
    )
    row += 1

    ctk.CTkLabel(parent, text=t("settings.theme"), font=ctk.CTkFont(size=13)).grid(
        row=row, column=0, sticky=s, pady=(0, 4)
    )
    row += 1

    theme_labels = [t("settings.theme_system"), t("settings.theme_dark"), t("settings.theme_light")]
    current_theme = win._settings.get("theme", "system")
    theme_idx = _THEMES.index(current_theme) if current_theme in _THEMES else 0
    win._theme_var = ctk.StringVar(value=theme_labels[theme_idx])
    theme_menu = ctk.CTkSegmentedButton(
        parent, values=theme_labels, variable=win._theme_var,
        command=win._on_theme_change,
    )
    theme_menu.grid(row=row, column=0, sticky="ew", pady=(0, 12))
    row += 1

    ctk.CTkLabel(parent, text=t("settings.language"), font=ctk.CTkFont(size=13)).grid(
        row=row, column=0, sticky=s, pady=(0, 4)
    )
    row += 1

    available_langs = get_available_languages()
    win._lang_codes = [code for code, _ in available_langs]
    lang_labels = [name for _, name in available_langs]
    current_lang = win._settings.get("language", "en")
    current_lang_idx = win._lang_codes.index(current_lang) if current_lang in win._lang_codes else 0
    win._lang_var = ctk.StringVar(value=lang_labels[current_lang_idx])
    lang_menu = ctk.CTkOptionMenu(
        parent, variable=win._lang_var, values=lang_labels,
        command=win._on_language_change,
    )
    lang_menu.grid(row=row, column=0, sticky=s, pady=(0, 12))
    row += 1

    ctk.CTkLabel(parent, text=t("settings.ui_scale"), font=ctk.CTkFont(size=13)).grid(
        row=row, column=0, sticky=s, pady=(0, 4)
    )
    row += 1

    scale_frame = ctk.CTkFrame(parent, fg_color="transparent")
    scale_frame.grid(row=row, column=0, sticky="ew", pady=(0, 16))
    scale_frame.grid_columnconfigure(0, weight=1)

    current_scale = win._settings.get("ui_scale", 1.0)
    win._scale_var = ctk.DoubleVar(value=current_scale)
    win._scale_label = ctk.CTkLabel(
        scale_frame, text=f"{int(current_scale * 100)}%", font=ctk.CTkFont(size=12),
        width=45,
    )
    win._scale_label.grid(row=0, column=1, padx=(8, 0))

    scale_slider = ctk.CTkSlider(
        scale_frame, from_=0.8, to=1.5, number_of_steps=14,
        variable=win._scale_var, command=win._on_scale_change,
    )
    scale_slider.grid(row=0, column=0, sticky="ew")
    row += 1

    sep = ctk.CTkFrame(parent, height=2, fg_color="gray70")
    sep.grid(row=row, column=0, sticky="ew", pady=8)
    row += 1

    return row


def build_download_section(win: SettingsWindow, parent: ctk.CTkFrame, start_row: int) -> int:
    row = start_row
    s = "e" if is_rtl() else "w"

    ctk.CTkLabel(parent, text=t("settings.download_defaults"), font=ctk.CTkFont(size=16, weight="bold")).grid(
        row=row, column=0, sticky=s, pady=(8, 12)
    )
    row += 1

    ctk.CTkLabel(parent, text=t("settings.speed_limit"), font=ctk.CTkFont(size=13)).grid(
        row=row, column=0, sticky=s, pady=(0, 4)
    )
    row += 1

    win._speed_entry = ctk.CTkEntry(parent, placeholder_text=t("settings.speed_limit_placeholder"))
    current_speed = win._settings.get("speed_limit", "")
    if current_speed:
        win._speed_entry.insert(0, current_speed)
    win._speed_entry.grid(row=row, column=0, sticky="ew", pady=(0, 12))
    win._speed_entry.bind("<FocusOut>", lambda _: win._save_text_field("speed_limit", win._speed_entry))
    win._speed_entry.bind("<Return>", lambda _: win._save_text_field("speed_limit", win._speed_entry))
    row += 1

    ctk.CTkLabel(parent, text=t("settings.simultaneous"), font=ctk.CTkFont(size=13)).grid(
        row=row, column=0, sticky=s, pady=(0, 4)
    )
    row += 1

    concurrency_frame = ctk.CTkFrame(parent, fg_color="transparent")
    concurrency_frame.grid(row=row, column=0, sticky="ew", pady=(0, 12))
    concurrency_frame.grid_columnconfigure(0, weight=1)

    current_concurrency = int(win._settings.get("max_concurrent_downloads", 3))
    win._concurrency_var = ctk.IntVar(value=current_concurrency)
    win._concurrency_label = ctk.CTkLabel(
        concurrency_frame, text=str(current_concurrency), font=ctk.CTkFont(size=12),
        width=30,
    )
    win._concurrency_label.grid(row=0, column=1, padx=(8, 0))

    concurrency_slider = ctk.CTkSlider(
        concurrency_frame, from_=1, to=5, number_of_steps=4,
        variable=win._concurrency_var, command=win._on_concurrency_change,
    )
    concurrency_slider.grid(row=0, column=0, sticky="ew")
    row += 1

    win._embed_thumb_var = ctk.BooleanVar(value=win._settings.get("embed_thumbnail", False))
    ctk.CTkCheckBox(
        parent, text=t("settings.embed_thumbnail"),
        variable=win._embed_thumb_var, font=ctk.CTkFont(size=13),
        command=lambda: win._save_bool("embed_thumbnail", win._embed_thumb_var),
    ).grid(row=row, column=0, sticky=s, pady=(0, 6))
    row += 1

    win._embed_meta_var = ctk.BooleanVar(value=win._settings.get("embed_metadata", False))
    ctk.CTkCheckBox(
        parent, text=t("settings.embed_metadata"),
        variable=win._embed_meta_var, font=ctk.CTkFont(size=13),
        command=lambda: win._save_bool("embed_metadata", win._embed_meta_var),
    ).grid(row=row, column=0, sticky=s, pady=(0, 6))
    row += 1

    ctk.CTkLabel(parent, text=t("settings.subtitle_languages"), font=ctk.CTkFont(size=13)).grid(
        row=row, column=0, sticky=s, pady=(6, 4)
    )
    row += 1

    win._subtitle_lang_entry = ctk.CTkEntry(parent, placeholder_text=t("settings.subtitle_languages_placeholder"))
    current_langs = win._settings.get("subtitle_languages", "en")
    if current_langs:
        win._subtitle_lang_entry.insert(0, current_langs)
    win._subtitle_lang_entry.grid(row=row, column=0, sticky="ew", pady=(0, 12))
    win._subtitle_lang_entry.bind("<FocusOut>", lambda _: win._save_text_field("subtitle_languages", win._subtitle_lang_entry))
    win._subtitle_lang_entry.bind("<Return>", lambda _: win._save_text_field("subtitle_languages", win._subtitle_lang_entry))
    row += 1

    win._clip_var = ctk.BooleanVar(value=win._settings.get("clipboard_monitor", False))
    ctk.CTkCheckBox(
        parent, text=t("settings.clipboard_monitor"),
        variable=win._clip_var, font=ctk.CTkFont(size=13),
        command=win._on_clipboard_toggle,
    ).grid(row=row, column=0, sticky=s, pady=(0, 16))
    row += 1

    sep = ctk.CTkFrame(parent, height=2, fg_color="gray70")
    sep.grid(row=row, column=0, sticky="ew", pady=8)
    row += 1

    return row


def build_network_section(win: SettingsWindow, parent: ctk.CTkFrame, start_row: int) -> int:
    row = start_row
    s = "e" if is_rtl() else "w"

    ctk.CTkLabel(parent, text=t("settings.network"), font=ctk.CTkFont(size=16, weight="bold")).grid(
        row=row, column=0, sticky=s, pady=(8, 12)
    )
    row += 1

    ctk.CTkLabel(parent, text=t("settings.proxy"), font=ctk.CTkFont(size=13)).grid(
        row=row, column=0, sticky=s, pady=(0, 4)
    )
    row += 1

    win._proxy_entry = ctk.CTkEntry(parent, placeholder_text=t("settings.proxy_placeholder"))
    current_proxy = win._settings.get("proxy", "")
    if current_proxy:
        win._proxy_entry.insert(0, current_proxy)
    win._proxy_entry.grid(row=row, column=0, sticky="ew", pady=(0, 12))
    win._proxy_entry.bind("<FocusOut>", lambda _: win._save_text_field("proxy", win._proxy_entry))
    win._proxy_entry.bind("<Return>", lambda _: win._save_text_field("proxy", win._proxy_entry))
    row += 1

    ctk.CTkLabel(parent, text=t("settings.browser_cookies"), font=ctk.CTkFont(size=13)).grid(
        row=row, column=0, sticky=s, pady=(0, 4)
    )
    row += 1

    current_browser = win._settings.get("browser_cookies", "")
    browser_idx = _BROWSERS.index(current_browser) if current_browser in _BROWSERS else 0
    win._browser_var = ctk.StringVar(value=_BROWSER_LABELS[browser_idx])
    browser_menu = ctk.CTkOptionMenu(
        parent, variable=win._browser_var, values=_BROWSER_LABELS,
        command=win._on_browser_change,
    )
    browser_menu.grid(row=row, column=0, sticky=s, pady=(0, 2))
    row += 1

    ctk.CTkLabel(
        parent,
        text=t("settings.browser_cookies_help"),
        font=ctk.CTkFont(size=11), text_color="gray", justify="right" if is_rtl() else "left",
    ).grid(row=row, column=0, sticky=s, pady=(0, 12))
    row += 1

    ctk.CTkLabel(parent, text=t("settings.cookie_file"), font=ctk.CTkFont(size=13)).grid(
        row=row, column=0, sticky=s, pady=(0, 4)
    )
    row += 1

    cookie_frame = ctk.CTkFrame(parent, fg_color="transparent")
    cookie_frame.grid(row=row, column=0, sticky="ew", pady=(0, 2))
    cookie_frame.grid_columnconfigure(0, weight=1)

    win._cookie_entry = ctk.CTkEntry(cookie_frame, placeholder_text=t("settings.cookie_file_placeholder"))
    current_cookie = win._settings.get("cookie_file", "")
    if current_cookie:
        win._cookie_entry.insert(0, current_cookie)
    win._cookie_entry.grid(row=0, column=0, sticky="ew")
    win._cookie_entry.bind("<FocusOut>", lambda _: win._save_text_field("cookie_file", win._cookie_entry))

    ctk.CTkButton(
        cookie_frame, text=t("settings.cookie_file_browse"), width=80,
        command=win._browse_cookie_file,
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


def build_advanced_section(win: SettingsWindow, parent: ctk.CTkFrame, start_row: int) -> int:
    row = start_row
    s = "e" if is_rtl() else "w"

    ctk.CTkLabel(parent, text=t("settings.advanced"), font=ctk.CTkFont(size=16, weight="bold")).grid(
        row=row, column=0, sticky=s, pady=(8, 12)
    )
    row += 1

    win._portable_var = ctk.BooleanVar(value=win._settings.get("portable_mode", False))
    ctk.CTkCheckBox(
        parent, text=t("settings.portable_mode"),
        variable=win._portable_var, font=ctk.CTkFont(size=13),
        command=win._on_portable_toggle,
    ).grid(row=row, column=0, sticky=s, pady=(0, 6))
    row += 1

    ctk.CTkLabel(
        parent,
        text=t("settings.portable_help"),
        font=ctk.CTkFont(size=11), text_color="gray",
    ).grid(row=row, column=0, sticky=s, pady=(0, 16))
    row += 1

    return row


def bind_mousewheel(scroll_frame: ctk.CTkScrollableFrame) -> None:
    """Propagate mousewheel events from all children to the scrollable frame."""
    canvas = scroll_frame._parent_canvas
    binding_in_progress = False

    def _on_mousewheel(event: Any) -> None:
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_recursive(widget: Any) -> None:
        with contextlib.suppress(NotImplementedError, AttributeError):
            widget.bind("<MouseWheel>", _on_mousewheel, add="+")
        try:
            children = widget.winfo_children()
        except Exception:
            return
        for child in children:
            _bind_recursive(child)

    def _on_map(_event: Any) -> None:
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
