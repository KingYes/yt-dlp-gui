import contextlib
import glob
import os
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

import yt_dlp

from .ffmpeg_utils import burn_subtitles_into_video, get_ffmpeg_location
from .format_parser import _AUDIO_FORMATS, FORMAT_PRESETS
from .utils import build_download_section_range, parse_rate_limit

_MAX_RETRIES = 2


class _FileProgressPoller:
    """Polls .part file size to synthesise progress events for range downloads.

    yt-dlp does not emit ``downloading`` progress-hook events when
    ``download_ranges`` is active.  This poller watches the output directory
    for ``.part`` files whose names start with *prefix*, samples their size
    every *interval* seconds, and calls *callback* with a synthetic progress
    dict that the UI can render like a normal download event.
    """

    def __init__(
        self,
        output_dir: str,
        callback: Callable[[dict], None],
        cancel_event: threading.Event,
        interval: float = 0.5,
    ) -> None:
        self._pattern = os.path.join(glob.escape(output_dir), "*.part")
        self._callback = callback
        self._cancel = cancel_event
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._prev_size = 0
        self._start_time = 0.0

    def start(self) -> None:
        self._stop.clear()
        self._start_time = time.monotonic()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set() and not self._cancel.is_set():
            total_size = 0
            for path in glob.glob(self._pattern):
                with contextlib.suppress(OSError):
                    total_size += os.path.getsize(path)
            if total_size > 0 and total_size != self._prev_size:
                elapsed = time.monotonic() - self._start_time
                speed = total_size / elapsed if elapsed > 0 else 0
                self._callback({
                    "status": "downloading",
                    "downloaded_bytes": total_size,
                    "total_bytes": 0,
                    "speed": speed,
                    "eta": 0,
                    "filename": "",
                    "title": "",
                })
                self._prev_size = total_size
            self._stop.wait(self._interval)


class DownloadManager:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._cancel_event = threading.Event()
        self._executor: ThreadPoolExecutor | None = None

    @property
    def is_busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _build_opts(
        self,
        format_key: str,
        output_dir: str,
        progress_callback: Callable[[dict], None],
        split_chapters: bool = False,
        playlist: bool = False,
        settings: dict[str, Any] | None = None,
        section_start: str = "",
        section_end: str = "",
        format_string: str = "",
        finished_files: list[str] | None = None,
        selected_chapters: list[str] | None = None,
        selected_subtitle_langs: list[str] | None = None,
    ) -> dict:
        """Build yt-dlp options with a progress hook baked in.

        If *finished_files* is provided, filenames from "finished" progress
        events are appended to it so callers can post-process them.
        """
        opts = self._build_base_opts(
            format_key, output_dir,
            split_chapters=split_chapters, playlist=playlist,
            settings=settings,
            section_start=section_start, section_end=section_end,
            format_string=format_string,
            selected_chapters=selected_chapters,
            selected_subtitle_langs=selected_subtitle_langs,
        )
        opts["progress_hooks"] = [
            lambda d: self._on_progress(d, progress_callback, finished_files=finished_files)
        ]
        opts["postprocessor_hooks"] = [
            lambda d: self._on_postprocessor(d, progress_callback)
        ]
        return opts

    def _build_base_opts(
        self,
        format_key: str,
        output_dir: str,
        split_chapters: bool = False,
        playlist: bool = False,
        settings: dict[str, Any] | None = None,
        section_start: str = "",
        section_end: str = "",
        format_string: str = "",
        selected_chapters: list[str] | None = None,
        selected_subtitle_langs: list[str] | None = None,
    ) -> dict:
        """Build yt-dlp options without progress hooks (caller adds them)."""
        if format_string:
            format_str = format_string
        else:
            format_str = FORMAT_PRESETS.get(format_key, "best")
        is_audio_only = format_key == "Audio Only (mp3)"
        settings = settings or {}

        if split_chapters:
            outtmpl = str(Path(output_dir) / "%(title)s - %(section_title)s.%(ext)s")
        elif playlist:
            outtmpl = str(Path(output_dir) / "%(playlist_title,title)s" / "%(title)s.%(ext)s")
        else:
            outtmpl = str(Path(output_dir) / "%(title)s.%(ext)s")

        ydl_opts: dict = {
            "format": format_str,
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": not playlist,
        }

        ffmpeg_loc = get_ffmpeg_location(settings.get("ffmpeg_path", ""))
        if ffmpeg_loc:
            ydl_opts["ffmpeg_location"] = ffmpeg_loc

        section_range = build_download_section_range(section_start, section_end)
        if section_range:
            ydl_opts["download_ranges"] = yt_dlp.utils.download_range_func(
                None, [section_range]
            )
            ydl_opts["force_keyframes_at_cuts"] = True
        elif selected_chapters:
            escaped = [re.escape(title) for title in selected_chapters]
            ydl_opts["download_ranges"] = yt_dlp.utils.download_range_func(
                escaped, None
            )

        rate = parse_rate_limit(settings.get("speed_limit", ""))
        if rate:
            ydl_opts["ratelimit"] = rate

        proxy = settings.get("proxy", "").strip()
        if proxy:
            ydl_opts["proxy"] = proxy

        browser = settings.get("browser_cookies", "").strip()
        if browser:
            ydl_opts["cookiesfrombrowser"] = (browser,)

        cookie_file = settings.get("cookie_file", "").strip()
        if cookie_file:
            ydl_opts["cookiefile"] = cookie_file

        postprocessors: list[dict] = []

        if is_audio_only:
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            })

        if split_chapters:
            postprocessors.append({"key": "FFmpegSplitChapters"})

        if settings.get("embed_thumbnail"):
            postprocessors.append({"key": "EmbedThumbnail"})

        if settings.get("embed_metadata"):
            postprocessors.append({"key": "FFmpegMetadata"})

        convert_format = settings.get("convert_format", "").strip()
        if convert_format and not is_audio_only:
            if convert_format in _AUDIO_FORMATS:
                postprocessors.append({
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": convert_format,
                    "preferredquality": "192",
                })
            else:
                postprocessors.append({
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": convert_format,
                })

        subtitle_mode = settings.get("subtitle_mode", "").strip()
        subtitle_burn = settings.get("subtitle_burn", False)
        if subtitle_mode or subtitle_burn or selected_subtitle_langs:
            if selected_subtitle_langs:
                lang_list = selected_subtitle_langs
            else:
                langs = settings.get("subtitle_languages", "en").strip() or "en"
                lang_list = [x.strip() for x in langs.split(",") if x.strip()]
            ydl_opts["writesubtitles"] = True
            ydl_opts["writeautomaticsub"] = True
            ydl_opts["subtitleslangs"] = lang_list
            ydl_opts["subtitlesformat"] = "srt/ass/best"

            if subtitle_mode == "embed" or subtitle_burn:
                postprocessors.append({"key": "FFmpegEmbedSubtitle"})

        if postprocessors:
            ydl_opts["postprocessors"] = postprocessors

        return ydl_opts

    def download(
        self,
        url: str,
        format_key: str,
        output_dir: str,
        progress_callback: Callable[[dict], None],
        done_callback: Callable[[str | None], None],
        split_chapters: bool = False,
        playlist: bool = False,
        settings: dict[str, Any] | None = None,
        section_start: str = "",
        section_end: str = "",
        format_string: str = "",
        selected_chapters: list[str] | None = None,
        selected_subtitle_langs: list[str] | None = None,
    ) -> None:
        """Start a single-URL download in a background thread."""
        if self.is_busy:
            done_callback("A download is already in progress.")
            return

        self._cancel_event.clear()
        settings = settings or {}
        do_burn = self._should_burn_subs(settings)
        finished_files: list[str] = []
        ydl_opts = self._build_opts(
            format_key, output_dir, progress_callback,
            split_chapters=split_chapters, playlist=playlist,
            settings=settings,
            section_start=section_start, section_end=section_end,
            format_string=format_string,
            finished_files=finished_files if do_burn else None,
            selected_chapters=selected_chapters,
            selected_subtitle_langs=selected_subtitle_langs,
        )

        poller: _FileProgressPoller | None = None
        if selected_chapters:
            poller = _FileProgressPoller(
                output_dir, progress_callback,
                self._cancel_event,
            )

        def _worker() -> None:
            if poller:
                poller.start()
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                if self._cancel_event.is_set():
                    done_callback("Download cancelled.")
                else:
                    if do_burn and finished_files:
                        for fpath in set(finished_files):
                            self._run_burn(fpath, settings)
                    done_callback(None)
            except Exception as exc:
                done_callback(str(exc))
            finally:
                if poller:
                    poller.stop()

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def download_batch(
        self,
        urls: list[str],
        format_key: str,
        output_dir: str,
        progress_callback: Callable[[dict], None],
        item_done_callback: Callable[[int, int, str | None], None],
        done_callback: Callable[[str | None], None],
        split_chapters: bool = False,
        playlist: bool = False,
        settings: dict[str, Any] | None = None,
        section_start: str = "",
        section_end: str = "",
        format_string: str = "",
        selected_chapters: list[str] | None = None,
        selected_subtitle_langs: list[str] | None = None,
    ) -> None:
        """Download multiple URLs sequentially in a background thread.

        item_done_callback(index, total, error) is called after each URL.
        done_callback(error) is called when all URLs finish or on cancellation.
        """
        if self.is_busy:
            done_callback("A download is already in progress.")
            return

        self._cancel_event.clear()
        settings = settings or {}
        do_burn = self._should_burn_subs(settings)
        finished_files: list[str] = []
        ydl_opts = self._build_opts(
            format_key, output_dir, progress_callback,
            split_chapters=split_chapters, playlist=playlist,
            settings=settings,
            section_start=section_start, section_end=section_end,
            format_string=format_string,
            finished_files=finished_files if do_burn else None,
            selected_chapters=selected_chapters,
            selected_subtitle_langs=selected_subtitle_langs,
        )
        total = len(urls)

        poller: _FileProgressPoller | None = None
        if selected_chapters:
            poller = _FileProgressPoller(
                output_dir, progress_callback,
                self._cancel_event,
            )

        def _worker() -> None:
            if poller:
                poller.start()
            try:
                for i, url in enumerate(urls, start=1):
                    if self._cancel_event.is_set():
                        done_callback("Download cancelled.")
                        return
                    last_exc: Exception | None = None
                    finished_files.clear()
                    for attempt in range(_MAX_RETRIES + 1):
                        if attempt > 0 and self._cancel_event.is_set():
                            done_callback("Download cancelled.")
                            return
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([url])
                            if self._cancel_event.is_set():
                                done_callback("Download cancelled.")
                                return
                            if do_burn and finished_files:
                                for fpath in set(finished_files):
                                    self._run_burn(fpath, settings)
                            item_done_callback(i, total, None)
                            last_exc = None
                            break
                        except Exception as exc:
                            last_exc = exc
                            if attempt < _MAX_RETRIES:
                                time.sleep(2)
                    if last_exc is not None:
                        item_done_callback(i, total, str(last_exc))
                done_callback(None)
            finally:
                if poller:
                    poller.stop()

        self._thread = threading.Thread(target=_worker, daemon=True)
        self._thread.start()

    def download_batch_concurrent(
        self,
        urls: list[str],
        format_key: str,
        output_dir: str,
        max_workers: int,
        progress_callback: Callable[[int, dict], None],
        item_done_callback: Callable[[int, int, str | None], None],
        done_callback: Callable[[str | None], None],
        split_chapters: bool = False,
        playlist: bool = False,
        settings: dict[str, Any] | None = None,
        section_start: str = "",
        section_end: str = "",
        format_string: str = "",
        selected_chapters: list[str] | None = None,
        selected_subtitle_langs: list[str] | None = None,
    ) -> None:
        """Download multiple URLs concurrently using a thread pool.

        progress_callback(item_index, data) is called with 0-based item index.
        item_done_callback(index_1based, total, error) is called after each URL.
        done_callback(error) is called when all URLs finish or on cancellation.
        """
        if self.is_busy:
            done_callback("A download is already in progress.")
            return

        self._cancel_event.clear()
        settings = settings or {}
        base_opts = self._build_base_opts(
            format_key, output_dir,
            split_chapters=split_chapters, playlist=playlist,
            settings=settings,
            section_start=section_start, section_end=section_end,
            format_string=format_string,
            selected_chapters=selected_chapters,
            selected_subtitle_langs=selected_subtitle_langs,
        )
        total = len(urls)
        do_burn = self._should_burn_subs(settings)

        def _coordinator() -> None:
            executor = ThreadPoolExecutor(max_workers=min(max_workers, total))
            self._executor = executor
            futures: list[tuple[int, Future[str | None]]] = []

            for idx, url in enumerate(urls):
                if self._cancel_event.is_set():
                    break
                future = executor.submit(
                    self._download_one, idx, url, base_opts, progress_callback,
                    settings=settings, burn_subs=do_burn,
                )
                futures.append((idx, future))

            cancelled = False
            for idx, future in futures:
                try:
                    error = future.result()
                except Exception as exc:
                    error = str(exc)

                if self._cancel_event.is_set() and not cancelled:
                    cancelled = True
                    executor.shutdown(wait=False, cancel_futures=True)

                item_done_callback(idx + 1, total, error)

            self._executor = None
            if cancelled or self._cancel_event.is_set():
                done_callback("Download cancelled.")
            else:
                done_callback(None)

        self._thread = threading.Thread(target=_coordinator, daemon=True)
        self._thread.start()

    def _download_one(
        self,
        idx: int,
        url: str,
        base_opts: dict,
        progress_callback: Callable[[int, dict], None],
        settings: dict[str, Any] | None = None,
        burn_subs: bool = False,
    ) -> str | None:
        """Download a single URL with retries. Returns error string or None."""
        finished_files: list[str] = []
        item_opts = dict(base_opts)
        item_opts["progress_hooks"] = [
            lambda d, _idx=idx: self._on_progress(
                d, lambda p: progress_callback(_idx, p),
                finished_files=finished_files if burn_subs else None,
            )
        ]

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            if self._cancel_event.is_set():
                return "Download cancelled."
            finished_files.clear()
            try:
                with yt_dlp.YoutubeDL(item_opts) as ydl:
                    ydl.download([url])
                if self._cancel_event.is_set():
                    return "Download cancelled."
                if burn_subs and finished_files and settings:
                    for fpath in set(finished_files):
                        self._run_burn(fpath, settings)
                return None
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    time.sleep(2)
        return str(last_exc) if last_exc else "Unknown error"

    def extract_info(
        self,
        url: str,
        callback: Callable[[dict | None, str | None], None],
        playlist: bool = False,
    ) -> None:
        """Fetch video metadata without downloading. Runs in a background thread.

        callback(info_dict, error) is called on completion.
        """
        opts: dict = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": not playlist,
            "skip_download": True,
        }

        def _worker() -> None:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                callback(info, None)
            except Exception as exc:
                callback(None, str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    def cancel(self) -> None:
        self._cancel_event.set()
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)

    @staticmethod
    def _should_burn_subs(settings: dict[str, Any] | None) -> bool:
        if not settings:
            return False
        return bool(settings.get("subtitle_burn")) and bool(
            settings.get("subtitle_mode", "") or settings.get("subtitle_burn")
        )

    @staticmethod
    def _run_burn(filename: str, settings: dict[str, Any]) -> str | None:
        """Run subtitle burn-in on a downloaded file. Returns error or None."""
        if not filename:
            return None
        ffmpeg_loc = get_ffmpeg_location(settings.get("ffmpeg_path", ""))
        ffmpeg_bin = None
        if ffmpeg_loc:
            import sys as _sys
            candidate = Path(ffmpeg_loc) / ("ffmpeg.exe" if _sys.platform == "win32" else "ffmpeg")
            if candidate.is_file():
                ffmpeg_bin = str(candidate)
        return burn_subtitles_into_video(filename, ffmpeg_path=ffmpeg_bin)

    def _on_progress(
        self,
        data: dict,
        callback: Callable[[dict], None],
        finished_files: list[str] | None = None,
    ) -> None:
        if self._cancel_event.is_set():
            raise yt_dlp.utils.DownloadError("Cancelled by user")

        info = data.get("info_dict") or {}
        filename = data.get("filename", "")
        progress = {
            "status": data.get("status", ""),
            "downloaded_bytes": data.get("downloaded_bytes", 0),
            "total_bytes": data.get("total_bytes") or data.get("total_bytes_estimate") or 0,
            "speed": data.get("speed", 0),
            "eta": data.get("eta", 0),
            "filename": filename,
            "title": info.get("title", ""),
            "duration": info.get("duration"),
        }
        callback(progress)

        if data.get("status") == "finished" and filename and finished_files is not None:
            finished_files.append(filename)

    @staticmethod
    def _on_postprocessor(
        data: dict,
        callback: Callable[[dict], None],
    ) -> None:
        status = data.get("status", "")
        postprocessor = data.get("postprocessor", "")
        info = data.get("info_dict") or {}
        if status == "started":
            callback({
                "status": "postprocessing",
                "postprocessor": postprocessor,
                "filename": info.get("filepath", ""),
                "title": info.get("title", ""),
            })


from .format_parser import (  # noqa: E402, F401 -- backward compat re-exports
    build_format_string,
    parse_chapters,
    parse_formats,
    parse_subtitles,
)
