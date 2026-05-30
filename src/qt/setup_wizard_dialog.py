"""Qt first-run FFmpeg setup wizard."""

from __future__ import annotations

import contextlib
import os
import platform
import tempfile
import threading
import zipfile
from collections.abc import Callable
from pathlib import Path

import tarfile
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import t
from ..ffmpeg_installer import (
    extract_btbn_archive,
    extract_evermeet_zip,
    get_download_urls,
    verify_ffmpeg,
)
from ..state import AppState
from ..utils import get_bin_dir

_CHUNK_SIZE = 64 * 1024


class SetupWizardDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        state: AppState,
        *,
        on_complete: Callable[[], None],
        schedule_on_main: Callable[[Callable[[], None]], None],
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._on_complete = on_complete
        self._schedule_on_main = schedule_on_main
        self._downloading = False

        self.setWindowTitle(t("wizard.title"))
        self.setFixedSize(480, 280)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("wizard.heading"), alignment=Qt.AlignmentFlag.AlignCenter))
        desc = QLabel(t("wizard.description"))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        self._install_btn = QPushButton(t("wizard.install"))
        self._install_btn.clicked.connect(self._start_install)
        btn_row.addWidget(self._install_btn)
        self._skip_btn = QPushButton(t("wizard.skip"))
        self._skip_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._skip_btn)
        layout.addLayout(btn_row)

    def _start_install(self) -> None:
        if self._downloading:
            return
        self._downloading = True
        self._install_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._progress.show()
        self._set_status(t("wizard.preparing"))
        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self) -> None:
        import requests

        urls = get_download_urls()
        if not urls:
            self._schedule_on_main(lambda: self._on_error(t("wizard.error_no_platform")))
            return

        bin_dir = get_bin_dir()
        bin_dir.mkdir(parents=True, exist_ok=True)
        is_macos = platform.system() == "Darwin"

        try:
            for i, url in enumerate(urls):
                self._schedule_on_main(
                    lambda u=url: self._set_status(t("wizard.downloading", name=Path(u).name or "ffmpeg"))
                )
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
                                self._schedule_on_main(
                                    lambda p=progress: self._progress.setValue(int(p * 100))
                                )

                    self._schedule_on_main(lambda: self._set_status(t("wizard.extracting")))

                    if is_macos:
                        extract_evermeet_zip(tmp_path, bin_dir)
                    else:
                        extract_btbn_archive(tmp_path, bin_dir)
                finally:
                    if tmp_path.exists():
                        tmp_path.unlink()

            self._schedule_on_main(lambda: self._set_status(t("wizard.verifying")))
            if not verify_ffmpeg(bin_dir):
                self._schedule_on_main(lambda: self._on_error(t("wizard.error_verification")))
                return

            ffmpeg_path = str(bin_dir)
            self._state.save_settings(ffmpeg_path=ffmpeg_path)
            os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

            self._schedule_on_main(self._on_success)

        except requests.RequestException as exc:
            self._schedule_on_main(lambda: self._on_error(t("wizard.error_download", error=exc)))
        except (zipfile.BadZipFile, tarfile.TarError) as exc:
            self._schedule_on_main(lambda: self._on_error(t("wizard.error_extraction", error=exc)))
        except OSError as exc:
            self._schedule_on_main(lambda: self._on_error(t("wizard.error_filesystem", error=exc)))

    def _suffix_for(self, url: str) -> str:
        if ".tar.xz" in url:
            return ".tar.xz"
        if ".tar.gz" in url:
            return ".tar.gz"
        return ".zip"

    def _set_status(self, text: str) -> None:
        self._status.setText(text)
        self._status.setStyleSheet("color: gray; font-size: 11px;")

    def _on_success(self) -> None:
        self._progress.setValue(100)
        self._set_status(t("wizard.success"))
        self._install_btn.setText(t("wizard.done"))
        self._install_btn.setEnabled(True)
        with contextlib.suppress(RuntimeError, TypeError):
            self._install_btn.clicked.disconnect()
        self._install_btn.clicked.connect(self._close_success)
        self._skip_btn.hide()

    def _on_error(self, message: str) -> None:
        self._downloading = False
        self._status.setText(message)
        self._status.setStyleSheet("color: #dc3545; font-size: 11px;")
        self._install_btn.setText(t("wizard.retry"))
        self._install_btn.setEnabled(True)
        self._skip_btn.setEnabled(True)

    def _close_success(self) -> None:
        self.accept()
        self._on_complete()
