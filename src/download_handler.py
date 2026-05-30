"""Download orchestration: start, progress, completion, retry logic."""

from __future__ import annotations

import os
from collections.abc import Callable

from .download_context import DownloadContext, DownloadFormState
from .download_manager import DownloadManager
from .i18n import t


class DownloadHandler:
    """Bridges the UI with DownloadManager, handling callbacks thread-safely."""

    def __init__(
        self,
        context: DownloadContext,
        manager: DownloadManager,
        schedule_on_main: Callable[[Callable[[], None]], None],
    ) -> None:
        self._ctx = context
        self._manager = manager
        self._schedule = schedule_on_main

    def start_download(self, urls: list[str], playlist: bool) -> None:
        form = self._ctx.get_form_state()
        os.makedirs(form.output_dir, exist_ok=True)

        self._ctx.prepare_download(
            urls,
            playlist=playlist,
            format_key=form.format_key,
            custom_format_enabled=form.custom_format_enabled,
        )
        self._ctx.save_last_input_from_form(urls, form)
        self._ctx.set_recent_folders(self._ctx.state.recent_folders)

        self._ctx.init_download_items(urls)
        self._log_start(form, urls, playlist)

        selected_chapters = self._ctx.get_selected_chapters()
        selected_subtitle_langs = self._ctx.get_selected_subtitle_langs()
        if selected_chapters:
            self._ctx.log(t("log.chapters_selected", count=len(selected_chapters)))

        self._ctx.reset_progress_start(selected_chapters=bool(selected_chapters))
        self._ctx.set_download_buttons_active(True)
        self._ctx.set_open_folder_enabled(False)

        self._run_batch(
            urls,
            form,
            playlist=playlist,
            selected_chapters=selected_chapters,
            selected_subtitle_langs=selected_subtitle_langs,
        )

    def start_download_from_entry(self, entry: dict) -> None:
        urls = entry["urls"]
        playlist = entry.get("playlist", False)
        format_key = entry.get("format_key", "Best (video+audio)")
        output_dir = entry.get("output_dir", self._ctx.output_dir)
        split_chapters = entry.get("split_chapters", False)
        custom_format_str = entry.get("custom_format_string", "")
        section_start = entry.get("section_start", "")
        section_end = entry.get("section_end", "")
        selected_chapters = entry.get("selected_chapters") or None
        selected_subtitle_langs = entry.get("selected_subtitle_langs") or None

        self._ctx.apply_queue_entry_settings(entry)
        os.makedirs(output_dir, exist_ok=True)

        self._ctx.prepare_download(
            urls,
            playlist=playlist,
            format_key=format_key,
            custom_format_enabled=bool(custom_format_str),
        )
        self._ctx.output_dir = output_dir
        self._ctx.init_download_items(urls)

        mode = t("log.download_mode_playlist") if playlist else t("log.download_mode_video")
        self._ctx.log(t("log.starting_queued", count=len(urls), mode=mode, format=format_key))
        self._ctx.reset_progress_start(selected_chapters=False)
        self._ctx.set_download_buttons_active(True)
        self._ctx.set_open_folder_enabled(False)

        def on_progress(data: dict) -> None:
            self._schedule(lambda d=data: self._ctx.apply_progress_update(d))

        def on_item_done(index: int, total: int, error: str | None) -> None:
            self._schedule(lambda: self._ctx.on_item_finished(index, total, error))

        def on_done(error: str | None) -> None:
            self._schedule(lambda: self._ctx.on_download_finished(error))

        self._manager.download_batch(
            urls,
            format_key,
            output_dir,
            progress_callback=on_progress,
            item_done_callback=on_item_done,
            done_callback=on_done,
            split_chapters=split_chapters,
            playlist=playlist,
            settings=self._ctx.state.settings,
            section_start=section_start,
            section_end=section_end,
            format_string=custom_format_str,
            selected_chapters=selected_chapters,
            selected_subtitle_langs=selected_subtitle_langs,
        )

    def retry_single_url(self, url: str, item_index: int) -> None:
        form = self._ctx.get_form_state()
        os.makedirs(form.output_dir, exist_ok=True)

        format_key = form.format_key
        split_chapters = form.split_chapters
        custom_format_str = form.custom_format_string if form.custom_format_enabled else ""

        self._ctx.set_download_buttons_active(True)

        def on_progress(data: dict) -> None:
            self._schedule(lambda d=data: self._ctx.apply_retry_progress(d, item_index))

        def on_item_done(index: int, total: int, error: str | None) -> None:
            self._schedule(lambda: self._ctx.on_retry_item_finished(item_index, error))

        def on_done(error: str | None) -> None:
            self._schedule(lambda: self._ctx.on_download_finished(error))

        self._manager.download_batch(
            [url],
            format_key,
            self._ctx.output_dir,
            split_chapters=split_chapters,
            playlist=self._ctx.is_playlist_download,
            progress_callback=on_progress,
            item_done_callback=on_item_done,
            done_callback=on_done,
            settings=self._ctx.state.settings,
            format_string=custom_format_str,
        )

    def _log_start(self, form: DownloadFormState, urls: list[str], playlist: bool) -> None:
        mode = t("log.download_mode_playlist") if playlist else t("log.download_mode_video")
        section_info = ""
        if form.download_section:
            s = form.section_start or "0:00"
            e = form.section_end or "end"
            section_info = t("log.section_info", start=s, end=e)
        format_display = form.custom_format_string if form.custom_format_enabled else form.format_key

        pp_parts: list[str] = []
        if form.convert_format != "None":
            pp_parts.append(t("log.pp_convert", fmt=form.convert_format))
        if form.subtitle_mode != "None":
            sub_val = form.subtitle_mode
            pp_parts.append(t("log.pp_embed_subs") if sub_val == "Embed" else t("log.pp_subs_file"))
        if form.subtitle_burn:
            pp_parts.append(t("log.pp_burn_subs"))
        pp_info = f" [{', '.join(pp_parts)}]" if pp_parts else ""

        self._ctx.log(
            t(
                "log.starting_download",
                count=len(urls),
                mode=mode,
                section=section_info,
                format=format_display,
                pp=pp_info,
            )
        )

    def _run_batch(
        self,
        urls: list[str],
        form: DownloadFormState,
        *,
        playlist: bool,
        selected_chapters: list[str] | None,
        selected_subtitle_langs: list[str] | None,
    ) -> None:
        def on_progress(data: dict) -> None:
            self._schedule(lambda d=data: self._ctx.apply_progress_update(d))

        def on_item_done(index: int, total: int, error: str | None) -> None:
            self._schedule(lambda: self._ctx.on_item_finished(index, total, error))

        def on_done(error: str | None) -> None:
            self._schedule(lambda: self._ctx.on_download_finished(error))

        self._manager.download_batch(
            urls,
            form.format_key,
            form.output_dir,
            progress_callback=on_progress,
            item_done_callback=on_item_done,
            done_callback=on_done,
            split_chapters=form.split_chapters,
            playlist=playlist,
            settings=self._ctx.state.settings,
            section_start=form.section_start,
            section_end=form.section_end,
            format_string=form.custom_format_string,
            selected_chapters=selected_chapters,
            selected_subtitle_langs=selected_subtitle_langs,
        )
