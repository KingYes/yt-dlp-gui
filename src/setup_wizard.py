import contextlib
import os
import platform
import queue
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import zipfile
from collections.abc import Callable
from pathlib import Path

import customtkinter as ctk
import requests

from .i18n import t
from .state import AppState
from .utils import get_bin_dir

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
            for tar_member in tf.getmembers():
                basename = Path(tar_member.name).name.lower()
                if basename in ("ffmpeg", "ffprobe") and tar_member.isfile():
                    reader = tf.extractfile(tar_member)
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
        self._main_queue: queue.Queue[Callable[[], None]] = queue.Queue()

        self.title(t("wizard.title"))
        self.geometry("480x280")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)

        self._build_ui()
        self._drain_main_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_skip)

    def _build_ui(self) -> None:
        ctk.CTkLabel(
            self,
            text=t("wizard.heading"),
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(24, 8))

        ctk.CTkLabel(
            self,
            text=t("wizard.description"),
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
            btn_frame, text=t("wizard.install"), width=140, command=self._start_install,
        )
        self._install_btn.grid(row=0, column=0, padx=(0, 12))

        self._skip_btn = ctk.CTkButton(
            btn_frame, text=t("wizard.skip"), width=80,
            fg_color="transparent", border_width=1, text_color=("gray30", "gray70"),
            command=self._on_skip,
        )
        self._skip_btn.grid(row=0, column=1)

    def _call_on_main(self, func: Callable[[], None]) -> None:
        """Schedule *func* to run on the main thread (thread-safe)."""
        self._main_queue.put(func)

    def _drain_main_queue(self) -> None:
        """Process pending callbacks from background threads (runs on main thread)."""
        while True:
            try:
                func = self._main_queue.get_nowait()
            except queue.Empty:
                break
            with contextlib.suppress(Exception):
                func()
        self.after(16, self._drain_main_queue)

    def _start_install(self) -> None:
        if self._downloading:
            return
        self._downloading = True
        self._install_btn.configure(state="disabled")
        self._skip_btn.configure(state="disabled")
        self._progress.grid()
        self._set_status(t("wizard.preparing"))

        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self) -> None:
        urls = get_download_urls()
        if not urls:
            self._call_on_main(lambda: self._on_error(t("wizard.error_no_platform")))
            return

        bin_dir = get_bin_dir()
        bin_dir.mkdir(parents=True, exist_ok=True)
        is_macos = platform.system() == "Darwin"

        try:
            for i, url in enumerate(urls):
                def _status_cb(u: str = url) -> None:
                    self._set_status(t("wizard.downloading", name=Path(u).name or "ffmpeg"))
                self._call_on_main(_status_cb)

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
                                def _prog_cb(p: float = progress) -> None:
                                    self._progress.set(p)
                                self._call_on_main(_prog_cb)

                    self._call_on_main(lambda: self._set_status(t("wizard.extracting")))

                    if is_macos:
                        _extract_evermeet_zip(tmp_path, bin_dir)
                    else:
                        _extract_btbn_archive(tmp_path, bin_dir)
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()

            self._call_on_main(lambda: self._set_status(t("wizard.verifying")))
            if not _verify_ffmpeg(bin_dir):
                self._call_on_main(lambda: self._on_error(t("wizard.error_verification")))
                return

            ffmpeg_path = str(bin_dir)
            self._state.save_settings(ffmpeg_path=ffmpeg_path)
            os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

            self._call_on_main(self._on_success)

        except requests.RequestException as exc:
            def _dl_err(e: Exception = exc) -> None:
                self._on_error(t("wizard.error_download", error=e))
            self._call_on_main(_dl_err)
        except (zipfile.BadZipFile, tarfile.TarError) as exc:
            def _ext_err(e: Exception = exc) -> None:
                self._on_error(t("wizard.error_extraction", error=e))
            self._call_on_main(_ext_err)
        except OSError as exc:
            def _fs_err(e: Exception = exc) -> None:
                self._on_error(t("wizard.error_filesystem", error=e))
            self._call_on_main(_fs_err)

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
        self._set_status(t("wizard.success"))
        self._install_btn.configure(text=t("wizard.done"), state="normal", command=self._close_success)
        self._skip_btn.grid_remove()

    def _on_error(self, message: str) -> None:
        self._downloading = False
        self._set_status(message)
        self._status_label.configure(text_color="red")
        self._install_btn.configure(text=t("wizard.retry"), state="normal")
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
