import os
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Callable

import customtkinter as ctk
import requests

from state import AppState
from utils import get_bin_dir

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
    # Fallback: try common aliases
    if system == "Windows":
        return _DOWNLOAD_URLS.get(("Windows", "AMD64"), [])
    if system == "Linux":
        return _DOWNLOAD_URLS.get(("Linux", "x86_64"), [])
    return []


def _extract_btbn_archive(archive_path: Path, dest_dir: Path) -> None:
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
            for member in tf.getmembers():
                basename = Path(member.name).name.lower()
                if basename in ("ffmpeg", "ffprobe") and member.isfile():
                    reader = tf.extractfile(member)
                    if reader:
                        target = dest_dir / basename
                        with open(target, "wb") as dst:
                            shutil.copyfileobj(reader, dst)
                        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _extract_evermeet_zip(archive_path: Path, dest_dir: Path) -> None:
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


def _verify_ffmpeg(bin_dir: Path) -> bool:
    """Run ffmpeg -version to verify the binary works."""
    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    ffmpeg_path = bin_dir / ffmpeg_name
    if not ffmpeg_path.is_file():
        return False
    try:
        result = subprocess.run(
            [str(ffmpeg_path), "-version"],
            capture_output=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


class SetupWizard(ctk.CTkToplevel):
    """First-run setup dialog that downloads FFmpeg automatically."""

    def __init__(self, master: ctk.CTk, state: AppState, on_complete: Callable[[], None]) -> None:
        super().__init__(master)

        self._state = state
        self._on_complete = on_complete
        self._downloading = False

        self.title("Setup Required")
        self.geometry("480x280")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_skip)

    def _build_ui(self) -> None:
        ctk.CTkLabel(
            self,
            text="FFmpeg Setup",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(24, 8))

        ctk.CTkLabel(
            self,
            text=(
                "FFmpeg is required for audio extraction, format merging,\n"
                "and other post-processing features.\n\n"
                "Click Install to download it automatically."
            ),
            font=ctk.CTkFont(size=13),
            justify="center",
        ).grid(row=1, column=0, padx=24, pady=(0, 16))

        self._progress = ctk.CTkProgressBar(self, width=380)
        self._progress.grid(row=2, column=0, padx=24, pady=(0, 4))
        self._progress.set(0)
        self._progress.grid_remove()

        self._status_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=11), text_color="gray",
        )
        self._status_label.grid(row=3, column=0, padx=24, pady=(0, 12))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=24, pady=(0, 24))

        self._install_btn = ctk.CTkButton(
            btn_frame, text="Install FFmpeg", width=140, command=self._start_install,
        )
        self._install_btn.grid(row=0, column=0, padx=(0, 12))

        self._skip_btn = ctk.CTkButton(
            btn_frame, text="Skip", width=80,
            fg_color="transparent", border_width=1, text_color=("gray30", "gray70"),
            command=self._on_skip,
        )
        self._skip_btn.grid(row=0, column=1)

    def _start_install(self) -> None:
        if self._downloading:
            return
        self._downloading = True
        self._install_btn.configure(state="disabled")
        self._skip_btn.configure(state="disabled")
        self._progress.grid()
        self._set_status("Preparing download...")

        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self) -> None:
        urls = get_download_urls()
        if not urls:
            self.after(0, lambda: self._on_error("No FFmpeg download available for this platform."))
            return

        bin_dir = get_bin_dir()
        bin_dir.mkdir(parents=True, exist_ok=True)
        is_macos = platform.system() == "Darwin"

        try:
            for i, url in enumerate(urls):
                self.after(0, lambda u=url: self._set_status(f"Downloading: {Path(u).name or 'ffmpeg'}..."))

                with tempfile.NamedTemporaryFile(delete=False, suffix=self._suffix_for(url)) as tmp:
                    tmp_path = Path(tmp.name)

                try:
                    resp = requests.get(url, stream=True, timeout=30)
                    resp.raise_for_status()
                    total = int(resp.headers.get("content-length", 0))
                    downloaded = 0

                    with open(tmp_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                progress = downloaded / total
                                if len(urls) > 1:
                                    progress = (i + progress) / len(urls)
                                self.after(0, lambda p=progress: self._progress.set(p))

                    self.after(0, lambda: self._set_status("Extracting..."))

                    if is_macos:
                        _extract_evermeet_zip(tmp_path, bin_dir)
                    else:
                        _extract_btbn_archive(tmp_path, bin_dir)
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()

            self.after(0, lambda: self._set_status("Verifying..."))
            if not _verify_ffmpeg(bin_dir):
                self.after(0, lambda: self._on_error("Verification failed — FFmpeg binary may be corrupted."))
                return

            # Persist the bin dir and update PATH
            ffmpeg_path = str(bin_dir)
            self._state.save_settings(ffmpeg_path=ffmpeg_path)
            os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

            self.after(0, self._on_success)

        except requests.RequestException as exc:
            self.after(0, lambda: self._on_error(f"Download failed: {exc}"))
        except (zipfile.BadZipFile, tarfile.TarError) as exc:
            self.after(0, lambda: self._on_error(f"Extraction failed: {exc}"))
        except OSError as exc:
            self.after(0, lambda: self._on_error(f"File system error: {exc}"))

    def _suffix_for(self, url: str) -> str:
        if ".tar.xz" in url:
            return ".tar.xz"
        if ".tar.gz" in url:
            return ".tar.gz"
        return ".zip"

    def _set_status(self, text: str) -> None:
        self._status_label.configure(text=text)

    def _on_success(self) -> None:
        self._progress.set(1.0)
        self._set_status("FFmpeg installed successfully!")
        self._install_btn.configure(text="Done", state="normal", command=self._close_success)
        self._skip_btn.grid_remove()

    def _on_error(self, message: str) -> None:
        self._downloading = False
        self._set_status(message)
        self._status_label.configure(text_color="red")
        self._install_btn.configure(text="Retry", state="normal")
        self._skip_btn.configure(state="normal")

    def _close_success(self) -> None:
        self.grab_release()
        self.destroy()
        self._on_complete()

    def _on_skip(self) -> None:
        if self._downloading:
            return
        self.grab_release()
        self.destroy()
