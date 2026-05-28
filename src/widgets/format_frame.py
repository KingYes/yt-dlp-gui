"""Format selection frame: preset/custom format, options, section, subtitles, chapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from ..format_parser import FORMAT_PRESETS
from ..i18n import t
from ..layout_utils import _anchor_start, _c, _pad_end, _pad_start, _sticky_end, _sticky_start


class FormatFrame(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkFrame,
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
        super().__init__(master)
        self.grid_columnconfigure(_c(1, 3), weight=1)

        ctk.CTkLabel(self, text=t("format.label"), font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=_c(0, 3), padx=_pad_start(12, 6), pady=(12, 4)
        )

        format_names = list(FORMAT_PRESETS.keys())
        self.format_var = ctk.StringVar(value=format_names[0])
        self.format_menu = ctk.CTkOptionMenu(
            self, variable=self.format_var, values=format_names, width=240
        )
        self.format_menu.grid(row=0, column=_c(1, 3), padx=4, pady=(12, 4), sticky=_sticky_start())

        self.download_btn = ctk.CTkButton(
            self, text=t("format.download"), width=130,
            fg_color="#28a745", hover_color="#218838",
            command=on_download,
        )
        self.download_btn.grid(row=0, column=_c(2, 3), padx=(4, 6), pady=(12, 4))

        self.cancel_btn = ctk.CTkButton(
            self, text=t("format.cancel"), width=80,
            fg_color="#dc3545", hover_color="#c82333",
            state="disabled", command=on_cancel,
        )
        self.cancel_btn.grid(row=0, column=_c(3, 3), padx=_pad_end(12, 4), pady=(12, 4))

        self.custom_format_var = ctk.BooleanVar(value=False)
        self._custom_format_checkbox = ctk.CTkCheckBox(
            self, text=t("format.custom_format"),
            variable=self.custom_format_var,
            font=ctk.CTkFont(size=13), command=on_custom_format_toggled,
        )
        self._custom_format_checkbox.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 4), sticky=_sticky_start())

        self.custom_format_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.custom_format_frame.grid_columnconfigure(_c(4, 4), weight=1)

        ctk.CTkLabel(
            self.custom_format_frame, text=t("format.video"), font=ctk.CTkFont(size=12),
        ).grid(row=0, column=_c(0, 4), padx=(0, 4))

        self.video_format_var = ctk.StringVar(value="")
        self.video_format_menu = ctk.CTkOptionMenu(
            self.custom_format_frame, variable=self.video_format_var,
            values=[t("format.preview_first")], width=260, state="disabled",
        )
        self.video_format_menu.grid(row=0, column=_c(1, 4), padx=(0, 12))

        ctk.CTkLabel(
            self.custom_format_frame, text=t("format.audio"), font=ctk.CTkFont(size=12),
        ).grid(row=0, column=_c(2, 4), padx=(0, 4))

        self.audio_format_var = ctk.StringVar(value="")
        self.audio_format_menu = ctk.CTkOptionMenu(
            self.custom_format_frame, variable=self.audio_format_var,
            values=[t("format.preview_first")], width=200, state="disabled",
        )
        self.audio_format_menu.grid(row=0, column=_c(3, 4), padx=(0, 8))

        self.format_status_label = ctk.CTkLabel(
            self.custom_format_frame, text="", font=ctk.CTkFont(size=11),
            text_color="gray", anchor=_anchor_start(),
        )
        self.format_status_label.grid(row=0, column=_c(4, 4), padx=(4, 0), sticky=_sticky_start())

        # Options row
        opts = ctk.CTkFrame(self, fg_color="transparent")
        opts.grid(row=3, column=0, columnspan=4, padx=12, pady=(0, 10), sticky="ew")
        opts.grid_columnconfigure(_c(3, 3), weight=1)

        self.split_chapters_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            opts, text=t("format.split_chapters"), variable=self.split_chapters_var,
            font=ctk.CTkFont(size=13),
        ).grid(row=0, column=_c(0, 3), padx=_pad_start(0, 16))

        self.section_var = ctk.BooleanVar(value=False)
        self.section_checkbox = ctk.CTkCheckBox(
            opts, text=t("format.download_section"), variable=self.section_var,
            font=ctk.CTkFont(size=13), command=on_section_toggled,
        )
        self.section_checkbox.grid(row=0, column=_c(1, 3), padx=_pad_start(0, 8))

        self.playlist_label = ctk.CTkLabel(
            opts, text="", anchor=_sticky_end(), font=ctk.CTkFont(size=12),
        )
        self.playlist_label.grid(row=0, column=_c(3, 3), sticky=_sticky_end())

        self.queue_label = ctk.CTkLabel(
            opts, text="", anchor=_sticky_end(), font=ctk.CTkFont(size=12), text_color="gray",
        )
        self.queue_label.grid(row=0, column=_c(2, 3), padx=(8, 8))

        # Section sub-frame
        self.section_frame = ctk.CTkFrame(opts, fg_color="transparent")
        self.section_frame.grid_columnconfigure(_c(4, 4), weight=1)

        ctk.CTkLabel(
            self.section_frame, text=t("format.section_start"), font=ctk.CTkFont(size=12),
        ).grid(row=0, column=_c(0, 4), padx=(0, 4))

        self.section_start_entry = ctk.CTkEntry(
            self.section_frame, width=90, font=ctk.CTkFont(size=12),
            placeholder_text=t("format.section_start_placeholder"),
        )
        self.section_start_entry.grid(row=0, column=_c(1, 4), padx=(0, 12))

        ctk.CTkLabel(
            self.section_frame, text=t("format.section_end"), font=ctk.CTkFont(size=12),
        ).grid(row=0, column=_c(2, 4), padx=(0, 4))

        self.section_end_entry = ctk.CTkEntry(
            self.section_frame, width=90, font=ctk.CTkFont(size=12),
            placeholder_text=t("format.section_end_placeholder"),
        )
        self.section_end_entry.grid(row=0, column=_c(3, 4), padx=(0, 12))

        self.section_error_label = ctk.CTkLabel(
            self.section_frame, text="", font=ctk.CTkFont(size=11),
            text_color="#dc3545", anchor=_anchor_start(),
        )
        self.section_error_label.grid(row=0, column=_c(4, 4), sticky=_sticky_start())

        # Post-processing row
        pp_frame = ctk.CTkFrame(self, fg_color="transparent")
        pp_frame.grid(row=4, column=0, columnspan=4, padx=12, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(pp_frame, text=t("format.convert"), font=ctk.CTkFont(size=12)).grid(
            row=0, column=_c(0, 4), padx=(0, 4)
        )

        convert_values = ["None", "MP4", "MKV", "WebM", "MP3", "AAC", "FLAC", "WAV", "OGG"]
        current_convert = settings.get("convert_format", "")
        convert_display = current_convert.upper() if current_convert else "None"
        if convert_display not in convert_values:
            convert_display = "None"
        self.convert_var = ctk.StringVar(value=convert_display)
        self.convert_menu = ctk.CTkOptionMenu(
            pp_frame, variable=self.convert_var, values=convert_values,
            width=90, command=on_convert_changed,
        )
        self.convert_menu.grid(row=0, column=_c(1, 4), padx=(0, 16))

        ctk.CTkLabel(pp_frame, text=t("format.subs"), font=ctk.CTkFont(size=12)).grid(
            row=0, column=_c(2, 4), padx=(0, 4)
        )

        sub_values = ["None", "Embed", "File"]
        current_sub = settings.get("subtitle_mode", "")
        sub_display = {"embed": "Embed", "file": "File"}.get(current_sub, "None")
        self.subtitle_mode_var = ctk.StringVar(value=sub_display)
        self.subtitle_mode_menu = ctk.CTkOptionMenu(
            pp_frame, variable=self.subtitle_mode_var, values=sub_values,
            width=90, command=on_subtitle_mode_changed,
        )
        self.subtitle_mode_menu.grid(row=0, column=_c(3, 4), padx=(0, 8))

        self.burn_sub_var = ctk.BooleanVar(value=settings.get("subtitle_burn", False))
        self._burn_sub_checkbox = ctk.CTkCheckBox(
            pp_frame, text=t("format.burn_subs"), variable=self.burn_sub_var,
            font=ctk.CTkFont(size=12), command=on_burn_sub_changed,
        )
        self._burn_sub_checkbox.grid(row=0, column=_c(4, 4), padx=(0, 8))

        # Subtitle summary row
        self.subtitle_summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.subtitle_summary_frame.grid_columnconfigure(_c(0, 1), weight=1)

        self.subtitle_summary_label = ctk.CTkLabel(
            self.subtitle_summary_frame, text=t("format.subtitle_none"),
            font=ctk.CTkFont(size=12), anchor=_anchor_start(),
        )
        self.subtitle_summary_label.grid(row=0, column=_c(0, 1), sticky=_sticky_start())

        ctk.CTkButton(
            self.subtitle_summary_frame, text=t("format.edit"), width=60, height=24,
            font=ctk.CTkFont(size=11), command=on_subtitle_edit,
        ).grid(row=0, column=_c(1, 1), padx=_pad_end(0, 8))

        # Chapter summary row
        self.chapter_summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.chapter_summary_frame.grid_columnconfigure(_c(0, 1), weight=1)

        self.chapter_summary_label = ctk.CTkLabel(
            self.chapter_summary_frame, text=t("format.chapters_all"),
            font=ctk.CTkFont(size=12), anchor=_anchor_start(),
        )
        self.chapter_summary_label.grid(row=0, column=_c(0, 1), sticky=_sticky_start())

        ctk.CTkButton(
            self.chapter_summary_frame, text=t("format.edit"), width=60, height=24,
            font=ctk.CTkFont(size=11), command=on_chapter_edit,
        ).grid(row=0, column=_c(1, 1), padx=_pad_end(0, 8))
