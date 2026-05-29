import json
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _resolve_state_dir() -> Path:
    """Use a portable config dir next to the executable if state.json exists there."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = Path(__file__).parent

    portable_file = exe_dir / "state.json"
    if portable_file.exists():
        return exe_dir

    return Path.home() / ".config" / "yt-dlp-gui"


_STATE_DIR = _resolve_state_dir()
_STATE_FILE = _STATE_DIR / "state.json"

_MAX_HISTORY = 100
_MAX_RECENT_FOLDERS = 5

_DEFAULT_STATE: dict[str, Any] = {
    "stats": {
        "total_downloads": 0,
        "total_audio_downloads": 0,
        "total_playlist_downloads": 0,
        "total_bytes": 0,
    },
    "last_input": {
        "urls": [],
        "output_dir": "",
        "format": "",
        "split_chapters": False,
        "download_section": False,
        "section_start": "",
        "section_end": "",
        "input_mode": "single",
        "progress_view": "simple",
        "custom_format_enabled": False,
        "video_format_id": "",
        "audio_format_id": "",
    },
    "history": [],
    "recent_folders": [],
    "window_geometry": "",
    "download_queue": [],
    "settings": {
        "theme": "system",
        "ui_scale": 1.0,
        "speed_limit": "",
        "embed_thumbnail": False,
        "embed_metadata": False,
        "clipboard_monitor": False,
        "proxy": "",
        "browser_cookies": "",
        "cookie_file": "",
        "portable_mode": False,
        "ffmpeg_path": "",
        "max_concurrent_downloads": 3,
        "convert_format": "",
        "subtitle_mode": "",
        "subtitle_languages": "en",
        "subtitle_burn": False,
        "language": "en",
    },
}


class AppState:
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._save_timer: threading.Timer | None = None
        self._save_lock = threading.Lock()
        self.load()

    def load(self) -> None:
        if _STATE_FILE.exists():
            try:
                self._data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

        for key, default in _DEFAULT_STATE.items():
            if key not in self._data:
                self._data[key] = default if not isinstance(default, dict) else dict(default)
            elif isinstance(default, dict):
                for sub_key, sub_default in default.items():
                    self._data[key].setdefault(sub_key, sub_default)

    def save(self) -> None:
        """Write state to disk immediately."""
        _STATE_DIR.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def save_debounced(self) -> None:
        """Schedule a debounced save (500ms). Multiple rapid calls collapse into one write."""
        with self._save_lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
            self._save_timer = threading.Timer(0.5, self.save)
            self._save_timer.daemon = True
            self._save_timer.start()

    def flush_pending_save(self) -> None:
        """Cancel any pending debounced save and write immediately."""
        with self._save_lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None
        self.save()

    # ---------------------------------------------------------------- Stats

    @property
    def stats(self) -> dict[str, int]:
        result: dict[str, int] = self._data["stats"]
        return result

    def record_download(
        self,
        bytes_downloaded: int,
        is_audio: bool = False,
        is_playlist: bool = False,
        title: str = "",
        url: str = "",
    ) -> None:
        s = self._data["stats"]
        s["total_downloads"] += 1
        s["total_bytes"] += bytes_downloaded
        if is_audio:
            s["total_audio_downloads"] += 1
        if is_playlist:
            s["total_playlist_downloads"] += 1

        self._append_history(title, url, bytes_downloaded, status="ok")
        self.save()

    def record_failed(self, title: str = "", url: str = "") -> None:
        self._append_history(title, url, 0, status="error")
        self.save()

    def _append_history(self, title: str, url: str, size: int, status: str) -> None:
        entry = {
            "title": title,
            "url": url,
            "date": datetime.now(UTC).isoformat(timespec="seconds"),
            "bytes": size,
            "status": status,
        }
        history = self._data["history"]
        history.append(entry)
        if len(history) > _MAX_HISTORY:
            self._data["history"] = history[-_MAX_HISTORY:]

    # ----------------------------------------------------------- Last Input

    @property
    def last_input(self) -> dict[str, Any]:
        result: dict[str, Any] = self._data["last_input"]
        return result

    def save_last_input(
        self,
        urls: list[str],
        output_dir: str,
        format_key: str,
        split_chapters: bool,
        input_mode: str = "single",
        progress_view: str = "simple",
        download_section: bool = False,
        section_start: str = "",
        section_end: str = "",
        custom_format_enabled: bool = False,
        video_format_id: str = "",
        audio_format_id: str = "",
    ) -> None:
        self._data["last_input"] = {
            "urls": urls,
            "output_dir": output_dir,
            "format": format_key,
            "split_chapters": split_chapters,
            "download_section": download_section,
            "section_start": section_start,
            "section_end": section_end,
            "input_mode": input_mode,
            "progress_view": progress_view,
            "custom_format_enabled": custom_format_enabled,
            "video_format_id": video_format_id,
            "audio_format_id": audio_format_id,
        }
        self.save()

    # -------------------------------------------------------- Recent Folders

    @property
    def recent_folders(self) -> list[str]:
        result: list[str] = self._data["recent_folders"]
        return result

    def add_recent_folder(self, folder: str) -> None:
        folders = self._data["recent_folders"]
        if folder in folders:
            folders.remove(folder)
        folders.insert(0, folder)
        self._data["recent_folders"] = folders[:_MAX_RECENT_FOLDERS]
        self.save()

    # ------------------------------------------------------ Window Geometry

    @property
    def window_geometry(self) -> str:
        result: str = self._data.get("window_geometry", "")
        return result

    @window_geometry.setter
    def window_geometry(self, value: str) -> None:
        self._data["window_geometry"] = value

    # ------------------------------------------------------------ History

    @property
    def history(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._data["history"]
        return result

    # --------------------------------------------------------- Download Queue

    @property
    def download_queue(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = self._data["download_queue"]
        return result

    def save_queue(self, entries: list[dict[str, Any]]) -> None:
        self._data["download_queue"] = entries
        self.save()

    def clear_queue(self) -> None:
        self._data["download_queue"] = []
        self.save()

    # ------------------------------------------------------------ Settings

    @property
    def settings(self) -> dict[str, Any]:
        result: dict[str, Any] = self._data["settings"]
        return result

    def save_settings(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if key in self._data["settings"]:
                self._data["settings"][key] = value
        self.save()

    def enable_portable_mode(self) -> None:
        """Switch to portable config: save state.json next to the executable."""
        global _STATE_DIR, _STATE_FILE
        if getattr(sys, "frozen", False):
            new_dir = Path(sys.executable).parent
        else:
            new_dir = Path(__file__).parent
        _STATE_DIR = new_dir
        _STATE_FILE = _STATE_DIR / "state.json"
        self._data["settings"]["portable_mode"] = True
        self.save()

    def disable_portable_mode(self) -> None:
        """Switch back to user config dir."""
        global _STATE_DIR, _STATE_FILE
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).parent
        else:
            exe_dir = Path(__file__).parent
        portable_file = exe_dir / "state.json"
        if portable_file.exists():
            portable_file.unlink()

        _STATE_DIR = Path.home() / ".config" / "yt-dlp-gui"
        _STATE_FILE = _STATE_DIR / "state.json"
        self._data["settings"]["portable_mode"] = False
        self.save()
