import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from .state import _STATE_DIR


def get_bin_dir() -> Path:
    """Return the directory where bundled binaries (FFmpeg) are stored."""
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
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
    )
