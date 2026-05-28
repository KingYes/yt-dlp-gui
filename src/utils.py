import re
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


from .ffmpeg_utils import (  # noqa: E402, F401 -- backward compat re-exports
    burn_subtitles_into_video,
    check_ffmpeg,
    get_bin_dir,
    get_ffmpeg_location,
    open_folder,
    send_notification,
)
