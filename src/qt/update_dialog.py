"""In-app update download and install dialog."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import t
from ..install_layout import resolve_install_root
from ..updater import UpdateCancelledError, download_and_stage_update
from .theme import danger_color, muted_color


class UpdateDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        manifest: dict[str, Any],
        version: str,
        *,
        schedule_on_main: Callable[[Callable[[], None]], None],
        on_ready_to_restart: Callable[[Path, Path], None],
    ) -> None:
        super().__init__(parent)
        self._manifest = manifest
        self._version = version
        self._schedule_on_main = schedule_on_main
        self._on_ready_to_restart = on_ready_to_restart
        self._cancel_event = threading.Event()
        self._working = False

        self.setWindowTitle(t("update.dialog_title"))
        self.setFixedSize(480, 220)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(t("update.dialog_heading", version=version), alignment=Qt.AlignmentFlag.AlignCenter))

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._status = QLabel(t("update.preparing"))
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(f"color: {muted_color().name()}; font-size: 11px;")
        layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        self._action_btn = QPushButton(t("update.install_now"))
        self._action_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self._action_btn)
        self._cancel_btn = QPushButton(t("update.cancel"))
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

        QTimer.singleShot(0, self._start_download)

    def _set_status(self, message: str) -> None:
        self._status.setText(message)

    def _set_progress(self, value: int) -> None:
        self._progress.setValue(max(0, min(100, value)))

    def _start_download(self) -> None:
        if self._working:
            return
        install_root = resolve_install_root()
        if install_root is None:
            QMessageBox.critical(self, t("app.title"), t("update.error_not_installed"))
            return

        self._working = True
        self._cancel_event.clear()
        self._action_btn.setEnabled(False)
        self._set_status(t("update.downloading"))
        threading.Thread(
            target=self._download_worker,
            args=(install_root,),
            daemon=True,
        ).start()

    def _download_worker(self, install_root: Path) -> None:
        def _progress(phase: str, current: int, total: int) -> None:
            if self._cancel_event.is_set():
                raise UpdateCancelledError

            def _update_ui() -> None:
                if phase == "download" and total > 0:
                    self._set_progress(int(current * 100 / total))
                elif phase == "wheel" and total > 0:
                    self._set_status(t("update.downloading_runtime", current=current, total=total))
                else:
                    self._set_status(t("update.downloading"))

            self._schedule_on_main(_update_ui)

        try:
            staging = download_and_stage_update(
                self._manifest,
                install_root,
                progress=_progress,
                should_cancel=self._cancel_event.is_set,
            )
        except UpdateCancelledError:
            self._schedule_on_main(self._on_cancelled)
            return
        except Exception as exc:
            message = str(exc)
            self._schedule_on_main(lambda: self._on_error(message))
            return

        self._schedule_on_main(lambda: self._on_success(install_root, staging))

    def _on_success(self, install_root: Path, staging: Path) -> None:
        self._working = False
        self._set_progress(100)
        self._set_status(t("update.complete"))
        self._cancel_btn.setText(t("update.dismiss"))
        self._action_btn.setEnabled(True)
        self._action_btn.setText(t("update.restart"))
        self._action_btn.clicked.disconnect()
        self._action_btn.clicked.connect(lambda: self._restart(install_root, staging))

    def _restart(self, install_root: Path, staging: Path) -> None:
        self._on_ready_to_restart(install_root, staging)
        self.accept()

    def _on_cancel(self) -> None:
        if self._working:
            self._cancel_event.set()
            self._set_status(t("update.cancelling"))
            return
        self.reject()

    def _on_cancelled(self) -> None:
        self._working = False
        self._action_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self._set_status(t("update.cancelled"))
        self._set_progress(0)

    def _on_error(self, message: str) -> None:
        self._working = False
        self._action_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self._set_status(t("update.error", error=message))
        self._status.setStyleSheet(f"color: {danger_color().name()}; font-size: 11px;")
