"""FFmpeg download and extraction (platform-specific archives)."""

from __future__ import annotations

import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

_CHUNK_SIZE = 64 * 1024

_BTBN_BASE = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest"

_DOWNLOAD_URLS: dict[tuple[str, str], list[str]] = {
    ("Windows", "AMD64"): [
        f"{_BTBN_BASE}/ffmpeg-master-latest-win64-gpl.zip",
    ],
    ("Windows", "x86_64"): [
        f"{_BTBN_BASE}/ffmpeg-master-latest-win64-gpl.zip",
    ],
    ("Linux", "x86_64"): [
        f"{_BTBN_BASE}/ffmpeg-master-latest-linux64-gpl.tar.xz",
    ],
    ("Linux", "aarch64"): [
        f"{_BTBN_BASE}/ffmpeg-master-latest-linuxarm64-gpl.tar.xz",
    ],
    ("Darwin", "arm64"): [
        "https://evermeet.cx/ffmpeg/get/zip",
        "https://evermeet.cx/ffmpeg/get/zip/ffprobe",
    ],
    ("Darwin", "x86_64"): [
        "https://evermeet.cx/ffmpeg/get/zip",
        "https://evermeet.cx/ffmpeg/get/zip/ffprobe",
    ],
}


def get_download_urls() -> list[str]:
    """Return download URLs for the current platform."""
    system = platform.system()
    machine = platform.machine()
    urls = _DOWNLOAD_URLS.get((system, machine))
    if urls:
        return urls
    if system == "Windows":
        return _DOWNLOAD_URLS.get(("Windows", "AMD64"), [])
    if system == "Linux":
        return _DOWNLOAD_URLS.get(("Linux", "x86_64"), [])
    return []


def extract_btbn_archive(archive_path: Path, dest_dir: Path) -> None:
    """Extract ffmpeg and ffprobe from a BtbN archive (zip or tar.xz)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = archive_path.name

    if name.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in zf.namelist():
                basename = Path(member).name.lower()
                if basename in ("ffmpeg.exe", "ffprobe.exe", "ffmpeg", "ffprobe"):
                    target = dest_dir / basename
                    with zf.open(member) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    if sys.platform != "win32":
                        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    elif name.endswith(".tar.xz") or name.endswith(".tar.gz"):
        with tarfile.open(archive_path, "r:*") as tf:
            for tar_member in tf.getmembers():
                basename = Path(tar_member.name).name.lower()
                if basename in ("ffmpeg", "ffprobe") and tar_member.isfile():
                    reader = tf.extractfile(tar_member)
                    if reader:
                        target = dest_dir / basename
                        with open(target, "wb") as dst:
                            shutil.copyfileobj(reader, dst)
                        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def extract_evermeet_zip(archive_path: Path, dest_dir: Path) -> None:
    """Extract a single binary from an evermeet.cx zip (macOS)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as zf:
        for member in zf.namelist():
            basename = Path(member).name.lower()
            if basename in ("ffmpeg", "ffprobe"):
                target = dest_dir / basename
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def verify_ffmpeg(bin_dir: Path) -> bool:
    """Run ffmpeg -version to verify the binary works."""
    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    ffmpeg_path = bin_dir / ffmpeg_name
    if not ffmpeg_path.is_file():
        return False
    try:
        result = subprocess.run(
            [str(ffmpeg_path), "-version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False
