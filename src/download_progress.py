"""Toolkit-neutral download progress and completion UI updates."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from .download_session import DownloadSession
from .i18n import t
from .utils import format_bytes, format_eta, format_speed, truncate_filename


class DownloadUIHost(Protocol):
    """Window surface required for progress updates (Qt MainWindow via QtDownloadContext)."""

    _progress: Any
    _download_session: DownloadSession
    _state: Any

    def _log(self, message: str) -> None: ...


def reset_progress_bar(host: DownloadUIHost, *, chapter_mode: bool) -> None:
    host._progress.progress_bar.set(0)
    if chapter_mode:
        host._progress.progress_bar.configure(mode="indeterminate")
        host._progress.progress_bar.start()
        host._progress.progress_detail.configure(text=t("progress.downloading_chapters"))


def apply_progress_update(host: DownloadUIHost, data: dict) -> None:
    session = host._download_session
    progress = host._progress

    if data.get("status") == "postprocessing":
        pp = data.get("postprocessor", "")
        progress.progress_detail.configure(
            text=t("progress.postprocessing", postprocessor=pp) if pp else t("progress.processing")
        )
        return

    if data.get("status") == "postprocessing_done":
        progress.progress_detail.configure(text=t("progress.postprocessing_done"))
        return

    if data.get("status") == "postprocessing_error":
        err = data.get("error", "")
        progress.progress_detail.configure(text=t("progress.postprocessing_error", error=err))
        return

    title = data.get("title")
    if title and title != session.video_title:
        session.video_title = title
        duration = data.get("duration")
        dur_str = ""
        if duration:
            m, s = divmod(int(duration), 60)
            dur_str = f" [{m}:{s:02d}]"
        progress.title_label.configure(text=f"{truncate_filename(title, 60)}{dur_str}")

    total = data["total_bytes"]
    downloaded = data["downloaded_bytes"]
    is_indeterminate = str(progress.progress_bar.cget("mode")) == "indeterminate"

    if total and total > 0:
        fraction = downloaded / total
        if not is_indeterminate:
            progress.progress_bar.set(fraction)
        pct = f"{fraction * 100:.1f}%"
    else:
        fraction = 0.0
        pct = format_bytes(downloaded)

    speed = format_speed(data["speed"])
    eta = format_eta(data["eta"])
    progress.progress_detail.configure(text=t("progress.detail", pct=pct, speed=speed, eta=eta))

    if data["status"] == "finished":
        session.accumulated_bytes += data["total_bytes"] or data["downloaded_bytes"]
        if is_indeterminate:
            progress.progress_bar.stop()
            progress.progress_bar.configure(mode="determinate")
        progress.progress_bar.set(1)
        progress.progress_detail.configure(text=t("progress.processing"))
        fraction = 1.0

    idx = session.current_item_index
    items = progress.download_items
    if idx < len(items):
        item = items[idx]
        item["status"] = "downloading"
        item["progress"] = fraction
        if title:
            item["title"] = title
        if data["status"] == "finished":
            item["progress"] = 1.0
            item["accumulated_bytes"] = session.accumulated_bytes
        if progress.progress_view == "detailed":
            progress.update_detail_row(idx)


def apply_retry_progress(host: DownloadUIHost, data: dict, item_index: int) -> None:
    progress = host._progress
    items = progress.download_items
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

    if progress.progress_view == "detailed":
        progress.update_detail_row(item_index)
    apply_progress_update(host, data)


def on_item_finished(
    host: DownloadUIHost,
    index: int,
    total: int,
    error: str | None,
    *,
    refresh_status: Callable[[], None],
) -> None:
    session = host._download_session
    progress = host._progress
    url = session.current_urls[index - 1] if index <= len(session.current_urls) else ""
    item_idx = index - 1
    items = progress.download_items

    if item_idx < len(items):
        item = items[item_idx]
        if error:
            item["status"] = "failed"
            item["error"] = error
        else:
            item["status"] = "done"
            item["progress"] = 1.0
        if progress.progress_view == "detailed":
            progress.update_detail_row(item_idx)

    session.current_item_index = index

    if session.input_mode == "multiple":
        done_count = sum(1 for it in items if it["status"] in ("done", "failed"))
        progress.overall_label.configure(
            text=t("progress.overall", done=done_count, total=session.total_items)
        )

    item_title = items[item_idx].get("title", "") if item_idx < len(items) else ""

    if error:
        host._log(t("log.item_error", index=index, total=total, error=error))
        host._state.record_failed(title=item_title or session.video_title, url=url)
    else:
        host._log(t("log.item_done", index=index, total=total))
        host._state.record_download(
            bytes_downloaded=session.accumulated_bytes,
            is_audio=session.is_audio_download,
            is_playlist=session.is_playlist_download,
            title=item_title or session.video_title,
            url=url,
        )
        session.accumulated_bytes = 0
        refresh_status()


def on_retry_item_finished(
    host: DownloadUIHost,
    item_index: int,
    error: str | None,
    *,
    refresh_status: Callable[[], None],
) -> None:
    session = host._download_session
    progress = host._progress
    items = progress.download_items
    if item_index >= len(items):
        return
    item = items[item_index]
    if error:
        item["status"] = "failed"
        item["error"] = error
        host._log(t("log.retry_failed", error=error))
        host._state.record_failed(title=item.get("title", ""), url=item["url"])
    else:
        item["status"] = "done"
        item["progress"] = 1.0
        host._log(t("log.retry_done", title=item.get("title") or item["url"]))
        host._state.record_download(
            bytes_downloaded=session.accumulated_bytes,
            is_audio=session.is_audio_download,
            is_playlist=session.is_playlist_download,
            title=item.get("title", ""),
            url=item["url"],
        )
        session.accumulated_bytes = 0
        refresh_status()

    if progress.progress_view == "detailed":
        progress.update_detail_row(item_index)


def on_download_finished(
    host: DownloadUIHost,
    error: str | None,
    output_dir: str,
    *,
    log: Callable[[str], None],
    refresh_status: Callable[[], None],
    schedule_queue: Callable[[], None],
    set_buttons_active: Callable[[bool], None],
    set_open_folder_enabled: Callable[[bool], None],
) -> None:
    from .ffmpeg_utils import send_notification

    session = host._download_session
    progress = host._progress
    progress.progress_bar.stop()
    progress.progress_bar.configure(mode="determinate")
    set_buttons_active(False)
    set_open_folder_enabled(True)
    if error:
        log(t("log.error", error=error))
        send_notification(t("app.title"), t("notify.download_failed", error=error))
    else:
        progress.progress_bar.set(1)
        progress.progress_detail.configure(text=t("progress.done"))
        log(t("log.all_complete", dir=output_dir))
        send_notification(t("app.title"), t("notify.all_complete"))

        if session.input_mode == "multiple" and session.total_items > 0:
            progress.overall_label.configure(
                text=t("progress.overall", done=session.total_items, total=session.total_items)
            )

    refresh_status()
    schedule_queue()
