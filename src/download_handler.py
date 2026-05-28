"""Download orchestration: start, progress, completion, retry logic."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .download_manager import DownloadManager
from .i18n import t
from .utils import format_bytes, format_eta, format_speed, truncate_filename

if TYPE_CHECKING:
    from .app import App


class DownloadHandler:
    """Bridges the App UI with DownloadManager, handling callbacks thread-safely."""

    def __init__(
        self,
        app: App,
        manager: DownloadManager,
        schedule_on_main: Callable[[Callable[[], None]], None],
    ) -> None:
        self._app = app
        self._manager = manager
        self._schedule = schedule_on_main

    def start_download(self, urls: list[str], playlist: bool) -> None:
        app = self._app
        os.makedirs(app._output_dir, exist_ok=True)

        format_key = app._fmt.format_var.get()
        split_chapters = app._fmt.split_chapters_var.get()
        download_section = app._fmt.section_var.get() and app._input_mode == "single"
        section_start = app._fmt.section_start_entry.get().strip() if download_section else ""
        section_end = app._fmt.section_end_entry.get().strip() if download_section else ""

        custom_format_str = ""
        video_format_id = ""
        audio_format_id = ""
        if app._custom_format_enabled:
            custom_format_str = app._get_custom_format_string()
            video_label = app._fmt.video_format_var.get()
            audio_label = app._fmt.audio_format_var.get()
            for f in app._available_video_formats:
                if f["label"] == video_label:
                    video_format_id = f["format_id"]
                    break
            for f in app._available_audio_formats:
                if f["label"] == audio_label:
                    audio_format_id = f["format_id"]
                    break

        app._is_playlist_download = playlist
        app._is_audio_download = format_key == "Audio Only (mp3)" and not app._custom_format_enabled
        app._accumulated_bytes = 0
        app._current_urls = urls
        app._concurrent_mode = False

        app._state.save_last_input(
            urls, app._output_dir, format_key, split_chapters,
            input_mode=app._input_mode, progress_view=app._progress.progress_view,
            download_section=download_section,
            section_start=section_start, section_end=section_end,
            custom_format_enabled=app._custom_format_enabled,
            video_format_id=video_format_id,
            audio_format_id=audio_format_id,
        )
        app._state.add_recent_folder(app._output_dir)

        app._init_download_items(urls)
        app._folder_menu.configure(values=app._state.recent_folders)

        mode = t("log.download_mode_playlist") if playlist else t("log.download_mode_video")
        section_info = ""
        if download_section:
            s = section_start or "0:00"
            e = section_end or "end"
            section_info = t("log.section_info", start=s, end=e)
        format_display = custom_format_str if app._custom_format_enabled else format_key

        pp_parts: list[str] = []
        convert_val = app._fmt.convert_var.get()
        if convert_val != "None":
            pp_parts.append(t("log.pp_convert", fmt=convert_val))
        sub_val = app._fmt.subtitle_mode_var.get()
        if sub_val != "None":
            pp_parts.append(t("log.pp_embed_subs") if sub_val == "Embed" else t("log.pp_subs_file"))
        if app._fmt.burn_sub_var.get():
            pp_parts.append(t("log.pp_burn_subs"))
        pp_info = f" [{', '.join(pp_parts)}]" if pp_parts else ""

        selected_chapters = app._get_selected_chapters()
        selected_subtitle_langs = app._get_selected_subtitle_langs()

        app._log(t("log.starting_download", count=len(urls), mode=mode, section=section_info, format=format_display, pp=pp_info))
        if selected_chapters:
            app._log(t("log.chapters_selected", count=len(selected_chapters)))
        app._tray.update_tooltip(t("notify.downloading", done=0, total=len(urls)))
        app._progress.progress_bar.set(0)
        if selected_chapters:
            app._progress.progress_bar.configure(mode="indeterminate")
            app._progress.progress_bar.start()
            app._progress.progress_detail.configure(text=t("progress.downloading_chapters"))
        app._fmt.download_btn.configure(state="disabled")
        app._fmt.cancel_btn.configure(state="normal")
        app._progress.open_folder_btn.configure(state="disabled")

        max_concurrent = int(app._state.settings.get("max_concurrent_downloads", 3))
        use_concurrent = max_concurrent > 1 and len(urls) > 1

        def on_item_done(index: int, total: int, error: str | None) -> None:
            self._schedule(lambda: self._item_finished(index, total, error))

        def on_done(error: str | None) -> None:
            self._schedule(lambda: self._download_finished(error))

        common_kwargs: dict[str, Any] = dict(
            split_chapters=split_chapters,
            playlist=playlist,
            item_done_callback=on_item_done,
            done_callback=on_done,
            settings=app._state.settings,
            section_start=section_start,
            section_end=section_end,
            format_string=custom_format_str,
            selected_chapters=selected_chapters,
            selected_subtitle_langs=selected_subtitle_langs,
        )

        if use_concurrent:
            app._concurrent_mode = True

            def on_progress_concurrent(item_index: int, data: dict) -> None:
                def _cb(idx: int = item_index, d: dict = data) -> None:
                    self._update_progress_concurrent(idx, d)
                self._schedule(_cb)

            self._manager.download_batch_concurrent(
                urls, format_key, app._output_dir,
                max_workers=max_concurrent,
                progress_callback=on_progress_concurrent,
                **common_kwargs,
            )
        else:
            def on_progress(data: dict) -> None:
                def _cb(d: dict = data) -> None:
                    self._update_progress(d)
                self._schedule(_cb)

            self._manager.download_batch(
                urls, format_key, app._output_dir,
                progress_callback=on_progress,
                **common_kwargs,
            )

    def start_download_from_entry(self, entry: dict) -> None:
        app = self._app
        urls = entry["urls"]
        playlist = entry.get("playlist", False)
        format_key = entry.get("format_key", "Best (video+audio)")
        output_dir = entry.get("output_dir", app._output_dir)
        split_chapters = entry.get("split_chapters", False)
        custom_format_str = entry.get("custom_format_string", "")
        section_start = entry.get("section_start", "")
        section_end = entry.get("section_end", "")
        selected_chapters = entry.get("selected_chapters") or None
        selected_subtitle_langs = entry.get("selected_subtitle_langs") or None

        if "convert_format" in entry:
            app._state.save_settings(
                convert_format=entry.get("convert_format", ""),
                subtitle_mode=entry.get("subtitle_mode", ""),
                subtitle_burn=entry.get("subtitle_burn", False),
            )

        os.makedirs(output_dir, exist_ok=True)

        app._is_playlist_download = playlist
        app._is_audio_download = format_key == "Audio Only (mp3)" and not custom_format_str
        app._accumulated_bytes = 0
        app._current_urls = urls
        app._concurrent_mode = False
        app._output_dir = output_dir

        app._init_download_items(urls)

        mode = t("log.download_mode_playlist") if playlist else t("log.download_mode_video")
        app._log(t("log.starting_queued", count=len(urls), mode=mode, format=format_key))
        app._progress.progress_bar.set(0)
        app._fmt.download_btn.configure(state="disabled")
        app._fmt.cancel_btn.configure(state="normal")
        app._progress.open_folder_btn.configure(state="disabled")

        max_concurrent = int(app._state.settings.get("max_concurrent_downloads", 3))
        use_concurrent = max_concurrent > 1 and len(urls) > 1

        def on_item_done(index: int, total: int, error: str | None) -> None:
            self._schedule(lambda: self._item_finished(index, total, error))

        def on_done(error: str | None) -> None:
            self._schedule(lambda: self._download_finished(error))

        common_kwargs: dict[str, Any] = dict(
            split_chapters=split_chapters,
            playlist=playlist,
            item_done_callback=on_item_done,
            done_callback=on_done,
            settings=app._state.settings,
            section_start=section_start,
            section_end=section_end,
            format_string=custom_format_str,
            selected_chapters=selected_chapters,
            selected_subtitle_langs=selected_subtitle_langs,
        )

        if use_concurrent:
            app._concurrent_mode = True

            def on_progress_concurrent(item_index: int, data: dict) -> None:
                def _cb(idx: int = item_index, d: dict = data) -> None:
                    self._update_progress_concurrent(idx, d)
                self._schedule(_cb)

            self._manager.download_batch_concurrent(
                urls, format_key, output_dir,
                max_workers=max_concurrent,
                progress_callback=on_progress_concurrent,
                **common_kwargs,
            )
        else:
            def on_progress(data: dict) -> None:
                def _cb(d: dict = data) -> None:
                    self._update_progress(d)
                self._schedule(_cb)

            self._manager.download_batch(
                urls, format_key, output_dir,
                progress_callback=on_progress,
                **common_kwargs,
            )

    def retry_single_url(self, url: str, item_index: int) -> None:
        app = self._app
        os.makedirs(app._output_dir, exist_ok=True)

        format_key = app._fmt.format_var.get()
        split_chapters = app._fmt.split_chapters_var.get()
        custom_format_str = app._get_custom_format_string() if app._custom_format_enabled else ""

        app._fmt.download_btn.configure(state="disabled")
        app._fmt.cancel_btn.configure(state="normal")

        def on_progress(data: dict) -> None:
            def _cb(d: dict = data) -> None:
                self._update_retry_progress(d, item_index)
            self._schedule(_cb)

        def on_item_done(index: int, total: int, error: str | None) -> None:
            self._schedule(lambda: self._retry_item_finished(item_index, error))

        def on_done(error: str | None) -> None:
            self._schedule(lambda: self._download_finished(error))

        self._manager.download_batch(
            [url], format_key, app._output_dir,
            split_chapters=split_chapters,
            playlist=app._is_playlist_download,
            progress_callback=on_progress,
            item_done_callback=on_item_done,
            done_callback=on_done,
            settings=app._state.settings,
            format_string=custom_format_str,
        )

    # ----------------------------------------------------------- Progress updates

    def _update_progress(self, data: dict) -> None:
        app = self._app
        if data.get("status") == "postprocessing":
            pp = data.get("postprocessor", "")
            app._progress.progress_detail.configure(
                text=t("progress.postprocessing", postprocessor=pp) if pp else t("progress.processing")
            )
            return

        title = data.get("title")
        if title and title != app._video_title:
            app._video_title = title
            duration = data.get("duration")
            dur_str = ""
            if duration:
                m, s = divmod(int(duration), 60)
                dur_str = f" [{m}:{s:02d}]"
            app._progress.title_label.configure(text=f"{truncate_filename(title, 60)}{dur_str}")

        total = data["total_bytes"]
        downloaded = data["downloaded_bytes"]
        is_indeterminate = str(app._progress.progress_bar.cget("mode")) == "indeterminate"

        if total and total > 0:
            fraction = downloaded / total
            if not is_indeterminate:
                app._progress.progress_bar.set(fraction)
            pct = f"{fraction * 100:.1f}%"
        else:
            fraction = 0
            pct = format_bytes(downloaded)

        speed = format_speed(data["speed"])
        eta = format_eta(data["eta"])
        app._progress.progress_detail.configure(text=t("progress.detail", pct=pct, speed=speed, eta=eta))

        if data["status"] == "finished":
            app._accumulated_bytes += data["total_bytes"] or data["downloaded_bytes"]
            if is_indeterminate:
                app._progress.progress_bar.stop()
                app._progress.progress_bar.configure(mode="determinate")
            app._progress.progress_bar.set(1)
            app._progress.progress_detail.configure(text=t("progress.processing"))
            fraction = 1.0

        idx = app._current_item_index
        items = app._progress.download_items
        if idx < len(items):
            item = items[idx]
            item["status"] = "downloading"
            item["progress"] = fraction
            if title:
                item["title"] = title
            if data["status"] == "finished":
                item["progress"] = 1.0
                item["accumulated_bytes"] = app._accumulated_bytes
            if app._progress.progress_view == "detailed":
                app._progress.update_detail_row(idx)

    def _update_progress_concurrent(self, item_index: int, data: dict) -> None:
        app = self._app
        items = app._progress.download_items
        if item_index >= len(items):
            return
        if data.get("status") == "postprocessing":
            return

        item = items[item_index]
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

        if app._progress.progress_view == "detailed":
            app._progress.update_detail_row(item_index)

        self._update_aggregate_progress(data)

    def _update_aggregate_progress(self, latest_data: dict) -> None:
        app = self._app
        items = app._progress.download_items
        if not items:
            return

        total_progress = sum(it["progress"] for it in items)
        aggregate = total_progress / len(items)
        app._progress.progress_bar.set(aggregate)

        active = [it for it in items if it["status"] == "downloading"]
        if active:
            latest_title = active[-1].get("title", "")
            if latest_title:
                app._video_title = latest_title

        title = latest_data.get("title")
        if title and title != app._video_title:
            app._video_title = title
        if app._video_title:
            duration = latest_data.get("duration")
            dur_str = ""
            if duration:
                m, s = divmod(int(duration), 60)
                dur_str = f" [{m}:{s:02d}]"
            app._progress.title_label.configure(text=f"{truncate_filename(app._video_title, 60)}{dur_str}")

        pct = f"{aggregate * 100:.1f}%"
        speed = format_speed(latest_data.get("speed", 0))
        eta = format_eta(latest_data.get("eta", 0))
        app._progress.progress_detail.configure(text=t("progress.detail", pct=pct, speed=speed, eta=eta))

    def _update_retry_progress(self, data: dict, item_index: int) -> None:
        app = self._app
        items = app._progress.download_items
        if item_index >= len(items):
            return
        item = items[item_index]
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

        if app._progress.progress_view == "detailed":
            app._progress.update_detail_row(item_index)
        self._update_progress(data)

    # ----------------------------------------------------------- Completion callbacks

    def _item_finished(self, index: int, total: int, error: str | None) -> None:
        app = self._app
        url = app._current_urls[index - 1] if index <= len(app._current_urls) else ""
        item_idx = index - 1
        items = app._progress.download_items

        if item_idx < len(items):
            item = items[item_idx]
            if error:
                item["status"] = "failed"
                item["error"] = error
            else:
                item["status"] = "done"
                item["progress"] = 1.0
            if app._progress.progress_view == "detailed":
                app._progress.update_detail_row(item_idx)

        if not app._concurrent_mode:
            app._current_item_index = index

        if app._input_mode == "multiple":
            done_count = sum(1 for it in items if it["status"] in ("done", "failed"))
            app._progress.overall_label.configure(text=t("progress.overall", done=done_count, total=app._total_items))
            app._tray.update_tooltip(t("notify.downloading", done=done_count, total=app._total_items))

        item_title = ""
        if item_idx < len(items):
            item_title = items[item_idx].get("title", "")

        if error:
            app._log(t("log.item_error", index=index, total=total, error=error))
            app._state.record_failed(title=item_title or app._video_title, url=url)
        else:
            app._log(t("log.item_done", index=index, total=total))
            if app._concurrent_mode:
                bytes_dl = items[item_idx]["accumulated_bytes"] if item_idx < len(items) else 0
            else:
                bytes_dl = app._accumulated_bytes
            app._state.record_download(
                bytes_downloaded=bytes_dl,
                is_audio=app._is_audio_download,
                is_playlist=app._is_playlist_download,
                title=item_title or app._video_title,
                url=url,
            )
            if not app._concurrent_mode:
                app._accumulated_bytes = 0
            app._refresh_status_bar()

    def _retry_item_finished(self, item_index: int, error: str | None) -> None:
        app = self._app
        items = app._progress.download_items
        if item_index >= len(items):
            return
        item = items[item_index]
        if error:
            item["status"] = "failed"
            item["error"] = error
            app._log(t("log.retry_failed", error=error))
            app._state.record_failed(title=item.get("title", ""), url=item["url"])
        else:
            item["status"] = "done"
            item["progress"] = 1.0
            app._log(t("log.retry_done", title=item.get("title") or item["url"]))
            app._state.record_download(
                bytes_downloaded=app._accumulated_bytes,
                is_audio=app._is_audio_download,
                is_playlist=app._is_playlist_download,
                title=item.get("title", ""),
                url=item["url"],
            )
            app._accumulated_bytes = 0
            app._refresh_status_bar()

        if app._progress.progress_view == "detailed":
            app._progress.update_detail_row(item_index)

    def _download_finished(self, error: str | None) -> None:
        from .ffmpeg_utils import send_notification

        app = self._app
        app._progress.progress_bar.stop()
        app._progress.progress_bar.configure(mode="determinate")
        app._fmt.download_btn.configure(state="normal")
        app._fmt.cancel_btn.configure(state="disabled")
        app._progress.open_folder_btn.configure(state="normal")
        if error:
            app._log(t("log.error", error=error))
            send_notification(t("app.title"), t("notify.download_failed", error=error))
        else:
            app._progress.progress_bar.set(1)
            app._progress.progress_detail.configure(text=t("progress.done"))
            app._log(t("log.all_complete", dir=app._output_dir))
            send_notification(t("app.title"), t("notify.all_complete"))

            if app._input_mode == "multiple" and app._total_items > 0:
                app._progress.overall_label.configure(
                    text=t("progress.overall", done=app._total_items, total=app._total_items)
                )

        app._tray.update_tooltip(t("tray.tooltip"))
        app._refresh_status_bar()

        app.after(100, app._process_queue)
