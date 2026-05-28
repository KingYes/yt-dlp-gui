import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
    r"localhost|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)

_PLAYLIST_ONLY_PATHS = re.compile(
    r"/playlist\b|/c/|/channel/|/@[^/]+/playlists",
    re.IGNORECASE,
)


def is_valid_url(url: str) -> bool:
    return bool(_URL_PATTERN.match(url.strip()))


def classify_url(url: str) -> str:
    """Return 'playlist', 'ambiguous', or 'video' for a given URL.

    - 'playlist':  URL that only makes sense as a playlist/channel.
    - 'ambiguous': URL has both a video ID and a playlist/list param.
    - 'video':     Plain single-video URL.
    """
    url = url.strip()
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    has_list = "list" in qs
    has_video = "v" in qs or "/shorts/" in parsed.path

    if _PLAYLIST_ONLY_PATHS.search(parsed.path):
        return "playlist"
    if has_list and has_video:
        return "ambiguous"
    if has_list:
        return "playlist"
    return "video"


def format_bytes(b: float | int | None) -> str:
    if b is None or b == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def format_speed(bps: float | int | None) -> str:
    if not bps:
        return "-- B/s"
    return f"{format_bytes(bps)}/s"


def format_eta(seconds: int | None) -> str:
    if not seconds or seconds < 0:
        return "--:--"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def truncate_filename(name: str, max_len: int = 50) -> str:
    if len(name) <= max_len:
        return name
    return name[: max_len - 3] + "..."


def parse_rate_limit(value: str) -> int | None:
    """Convert a human-readable rate string to bytes/sec.

    Accepts formats like "5M", "500K", "1G", "1000" (plain bytes).
    Returns None if empty or unparseable.
    """
    value = value.strip()
    if not value:
        return None

    multipliers = {"k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}
    suffix = value[-1].lower()
    if suffix in multipliers:
        try:
            return int(float(value[:-1]) * multipliers[suffix])
        except ValueError:
            return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_timestamp(value: str) -> float | None:
    """Parse a timestamp string into total seconds.

    Accepted formats: SS, MM:SS, HH:MM:SS, or fractional variants (e.g. 1:23.5).
    Returns None if the string is empty or unparseable.
    """
    value = value.strip()
    if not value:
        return None

    parts = value.split(":")
    try:
        if len(parts) == 1:
            secs = float(parts[0])
        elif len(parts) == 2:
            secs = float(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            secs = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        else:
            return None
    except ValueError:
        return None

    return secs if secs >= 0 else None


def format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS for display."""
    total = int(seconds)
    h, remainder = divmod(total, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def validate_time_range(
    start: str, end: str, duration: float | None = None,
) -> str | None:
    """Validate start/end timestamp strings and return an error message or None."""
    start_sec = parse_timestamp(start)
    end_sec = parse_timestamp(end)

    if start_sec is None and end_sec is None:
        return "Enter at least a start or end time."

    if start_sec is not None and end_sec is not None and start_sec >= end_sec:
        return "Start time must be before end time."

    if duration is not None:
        if start_sec is not None and start_sec >= duration:
            return f"Start time exceeds video duration ({format_timestamp(duration)})."
        if end_sec is not None and end_sec > duration:
            return f"End time exceeds video duration ({format_timestamp(duration)})."

    return None


def build_download_section_range(
    start: str, end: str,
) -> tuple[float, float] | None:
    """Build a (start_sec, end_sec) tuple for yt-dlp's download_ranges API.

    Returns None if both are empty. Uses 0 for missing start
    and float('inf') for missing end.
    """
    start_sec = parse_timestamp(start)
    end_sec = parse_timestamp(end)

    if start_sec is None and end_sec is None:
        return None

    return (start_sec or 0.0, end_sec if end_sec is not None else float("inf"))


def format_chapter_range(start: float, end: float) -> str:
    """Format a chapter time range like '1:23 - 4:56'."""
    return f"{format_timestamp(start)} - {format_timestamp(end)}"


def get_bin_dir() -> Path:
    """Return the directory where bundled binaries (FFmpeg) are stored."""
    from state import _STATE_DIR
    return _STATE_DIR / "bin"


def check_ffmpeg(custom_path: str = "") -> bool:
    """Check whether FFmpeg is available.

    Checks in order: explicit custom_path, app bin dir, system PATH.
    """
    if custom_path:
        p = Path(custom_path)
        if p.is_file() or (p.is_dir() and (p / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")).is_file()):
            return True

    bin_dir = get_bin_dir()
    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    if (bin_dir / ffmpeg_name).is_file():
        return True

    return shutil.which("ffmpeg") is not None


def get_ffmpeg_location(custom_path: str = "") -> str | None:
    """Return the FFmpeg directory path to pass as ffmpeg_location, or None if system PATH."""
    if custom_path:
        p = Path(custom_path)
        if p.is_file():
            return str(p.parent)
        if p.is_dir():
            return str(p)

    bin_dir = get_bin_dir()
    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    if (bin_dir / ffmpeg_name).is_file():
        return str(bin_dir)

    return None


def burn_subtitles_into_video(
    video_path: str, ffmpeg_path: str | None = None,
) -> str | None:
    """Burn embedded subtitles into the video stream by re-encoding.

    Looks for an embedded subtitle stream in the file and renders it onto
    the video.  Returns an error string or None on success.
    The original file is replaced in-place.
    """
    vpath = Path(video_path)
    if not vpath.is_file():
        return f"File not found: {video_path}"

    ffmpeg = ffmpeg_path or shutil.which("ffmpeg")
    if not ffmpeg:
        return "FFmpeg not found"

    tmp_path = vpath.with_stem(vpath.stem + "_burned")

    cmd = [
        ffmpeg, "-y", "-i", str(vpath),
        "-vf", f"subtitles={_escape_ffmpeg_path(str(vpath))}",
        "-c:a", "copy",
        str(tmp_path),
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600,
        )
        if result.returncode != 0:
            tmp_path.unlink(missing_ok=True)
            stderr_tail = result.stderr[-500:] if result.stderr else ""
            return f"FFmpeg failed (exit {result.returncode}): {stderr_tail}"

        tmp_path.replace(vpath)
        return None
    except subprocess.TimeoutExpired:
        tmp_path.unlink(missing_ok=True)
        return "FFmpeg timed out (>1 hour)"
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        return str(exc)


def _escape_ffmpeg_path(path: str) -> str:
    """Escape special characters in file paths for FFmpeg subtitle filter."""
    path = path.replace("\\", "/")
    path = path.replace(":", "\\:")
    path = path.replace("'", "\\'")
    return path


def open_folder(path: str) -> None:
    """Open a file or folder in the system file manager."""
    target = path if os.path.isdir(path) else os.path.dirname(path)
    system = platform.system()
    if system == "Darwin":
        subprocess.Popen(["open", target])
    elif system == "Windows":
        os.startfile(target)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", target])


def send_notification(title: str, message: str) -> None:
    """Fire an OS-level notification. Best-effort — silently ignores failures."""
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen([
                "osascript", "-e",
                f'display notification "{message}" with title "{title}"',
            ])
        elif system == "Windows":
            _win_toast(title, message)
        else:
            subprocess.Popen(["notify-send", title, message])
    except Exception:
        pass


def _win_toast(title: str, message: str) -> None:
    """Windows 10+ toast notification via PowerShell."""
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
        "ContentType = WindowsRuntime] > $null; "
        "$template = [Windows.UI.Notifications.ToastNotificationManager]::"
        "GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
        f'$template.GetElementsByTagName("text")[0].AppendChild($template.CreateTextNode("{title}")) > $null; '
        f'$template.GetElementsByTagName("text")[1].AppendChild($template.CreateTextNode("{message}")) > $null; '
        "$notifier = [Windows.UI.Notifications.ToastNotificationManager]::"
        'CreateToastNotifier("yt-dlp GUI"); '
        "$notifier.Show([Windows.UI.Notifications.ToastNotification]::new($template))"
    )
    subprocess.Popen(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps],
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
