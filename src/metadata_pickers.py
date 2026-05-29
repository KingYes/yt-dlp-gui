"""Subtitle, chapter, and format picker management for the main app."""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from .download_manager import build_format_string, parse_chapters, parse_formats, parse_subtitles
from .i18n import t

if TYPE_CHECKING:
    from .app import App


class MetadataPickerController:
    """Manages subtitle, chapter, and custom-format picker state."""

    def __init__(self, app: App) -> None:
        self._app = app

    # ---- Subtitle picker ----

    def populate_subtitles(self, info: dict) -> None:
        app = self._app
        subs = parse_subtitles(info)
        app._available_subtitles = subs
        app._subtitle_vars.clear()
        if not (subs["manual"] or subs["auto"]):
            app._fmt.subtitle_summary_frame.grid_forget()
            return
        for entry in subs["manual"]:
            app._subtitle_vars[entry["code"]] = ctk.BooleanVar(value=False)
        for entry in subs["auto"]:
            app._subtitle_vars[f"auto:{entry['code']}"] = ctk.BooleanVar(value=False)
        app._subtitle_select_all_var.set(False)
        self.update_subtitle_summary()
        app._fmt.subtitle_summary_frame.grid(row=5, column=0, columnspan=4, padx=12, pady=(0, 6), sticky="ew")

    def hide_subtitles(self) -> None:
        app = self._app
        app._fmt.subtitle_summary_frame.grid_forget()
        app._available_subtitles = {"manual": [], "auto": []}
        app._subtitle_vars.clear()
        if app._subtitle_dialog and app._subtitle_dialog.winfo_exists():
            app._subtitle_dialog.destroy()
        app._subtitle_dialog = None

    def update_subtitle_summary(self) -> None:
        app = self._app
        total = len(app._subtitle_vars)
        selected = sum(1 for v in app._subtitle_vars.values() if v.get())
        if selected == 0:
            text = t("format.subtitle_summary_none", total=total)
        elif selected == total:
            text = t("format.subtitle_summary_all", total=total)
        else:
            text = t("format.subtitle_summary_some", selected=selected, total=total)
        app._fmt.subtitle_summary_label.configure(text=text)

    def open_subtitle_dialog(self) -> None:
        app = self._app
        if app._subtitle_dialog and app._subtitle_dialog.winfo_exists():
            app._subtitle_dialog.focus()
            return
        from .widgets.subtitle_picker import SubtitlePickerDialog

        app._subtitle_dialog = SubtitlePickerDialog(
            app, app._available_subtitles, app._subtitle_vars,
            app._subtitle_select_all_var,
            on_close=self.update_subtitle_summary,
        )

    def get_selected_subtitle_langs(self) -> list[str] | None:
        app = self._app
        if not app._subtitle_vars:
            return None
        selected = []
        for key, var in app._subtitle_vars.items():
            if var.get():
                code = key.replace("auto:", "")
                if code not in selected:
                    selected.append(code)
        return selected if selected else None

    # ---- Chapter picker ----

    def populate_chapters(self, info: dict) -> None:
        app = self._app
        chapters = parse_chapters(info)
        app._available_chapters = chapters
        app._chapter_vars.clear()
        if not chapters:
            app._fmt.chapter_summary_frame.grid_forget()
            return
        for _ch in chapters:
            app._chapter_vars.append(ctk.BooleanVar(value=True))
        app._chapter_select_all_var.set(True)
        self.update_chapter_summary()
        app._fmt.chapter_summary_frame.grid(row=6, column=0, columnspan=4, padx=12, pady=(0, 6), sticky="ew")

    def hide_chapters(self) -> None:
        app = self._app
        app._fmt.chapter_summary_frame.grid_forget()
        app._available_chapters = []
        app._chapter_vars.clear()
        if app._chapter_dialog and app._chapter_dialog.winfo_exists():
            app._chapter_dialog.destroy()
        app._chapter_dialog = None

    def update_chapter_summary(self) -> None:
        app = self._app
        total = len(app._chapter_vars)
        selected = sum(1 for v in app._chapter_vars if v.get())
        if selected == total:
            text = t("format.chapter_summary_all", total=total)
        elif selected == 0:
            text = t("format.chapter_summary_none", total=total)
        else:
            text = t("format.chapter_summary_some", selected=selected, total=total)
        app._fmt.chapter_summary_label.configure(text=text)

    def open_chapter_dialog(self) -> None:
        app = self._app
        if app._chapter_dialog and app._chapter_dialog.winfo_exists():
            app._chapter_dialog.focus()
            return
        from .widgets.chapter_picker import ChapterPickerDialog

        app._chapter_dialog = ChapterPickerDialog(
            app, app._available_chapters, app._chapter_vars,
            app._chapter_select_all_var,
            on_close=self.update_chapter_summary,
        )

    def get_selected_chapters(self) -> list[str] | None:
        app = self._app
        if not app._chapter_vars or not app._available_chapters:
            return None
        selected = []
        all_selected = True
        for i, var in enumerate(app._chapter_vars):
            if var.get():
                selected.append(app._available_chapters[i]["title"])
            else:
                all_selected = False
        if all_selected:
            return None
        return selected if selected else None

    # ---- Format picker ----

    def populate_formats(self, info: dict) -> None:
        app = self._app
        video_formats, audio_formats = parse_formats(info)
        app._available_video_formats = video_formats
        app._available_audio_formats = audio_formats

        if video_formats:
            labels = [f["label"] for f in video_formats]
            app._fmt.video_format_menu.configure(values=labels, state="normal")
            app._fmt.video_format_var.set(labels[0])
        else:
            app._fmt.video_format_menu.configure(values=[t("format.none_available")], state="disabled")
            app._fmt.video_format_var.set(t("format.none_available"))

        if audio_formats:
            labels = [f["label"] for f in audio_formats]
            app._fmt.audio_format_menu.configure(values=labels, state="normal")
            app._fmt.audio_format_var.set(labels[0])
        else:
            app._fmt.audio_format_menu.configure(values=[t("format.none_available")], state="disabled")
            app._fmt.audio_format_var.set(t("format.none_available"))

        count_str = t("format.count", video=len(video_formats), audio=len(audio_formats))
        app._fmt.format_status_label.configure(text=count_str, text_color="#17a2b8")

    def get_custom_format_string(self) -> str:
        app = self._app
        video_id = ""
        audio_id = ""
        video_label = app._fmt.video_format_var.get()
        for f in app._available_video_formats:
            if f["label"] == video_label:
                video_id = f["format_id"]
                break
        audio_label = app._fmt.audio_format_var.get()
        for f in app._available_audio_formats:
            if f["label"] == audio_label:
                audio_id = f["format_id"]
                break
        return build_format_string(video_id, audio_id)
