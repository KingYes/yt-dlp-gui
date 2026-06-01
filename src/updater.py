"""Application update checks and in-app update installation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .install_layout import cache_dir, resolve_install_root, runtime_dir
from .pyside6_installer import (
    ProgressCallback,
    install_app_bundle,
    install_pyside6_wheels,
    load_manifest,
)

_GITHUB_REPO = "KingYes/yt-dlp-gui"
_RELEASES_URL = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"
_TIMEOUT = 10

APP_VERSION = "1.1.2"


class UpdateCancelledError(Exception):
    """Raised when the user cancels an in-progress update download."""


@dataclass(frozen=True)
class UpdateCheckResult:
    latest_version: str | None = None
    release_url: str | None = None
    manifest: dict[str, Any] | None = None
    in_app_available: bool = False


def _parse_version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in version.lstrip("v").split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def is_newer_version(latest: str, current: str) -> bool:
    return _parse_version_tuple(latest) > _parse_version_tuple(current)


def can_apply_in_app_update() -> bool:
    return sys.platform == "win32" and getattr(sys, "frozen", False) and resolve_install_root() is not None


def manifest_url_for_tag(tag: str) -> str:
    normalized = tag if tag.startswith("v") else f"v{tag}"
    return f"https://github.com/KingYes/yt-dlp-gui/releases/download/{normalized}/update-manifest.json"


def fetch_manifest_for_tag(tag: str) -> dict[str, Any]:
    return load_manifest(manifest_url_for_tag(tag))


def check_for_update(callback: Callable[[UpdateCheckResult], None]) -> None:
    """Check GitHub for a newer release in a background thread."""

    def _worker() -> None:
        result = UpdateCheckResult()
        try:
            import requests

            resp = requests.get(_RELEASES_URL, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            tag = data.get("tag_name", "")
            latest = tag.lstrip("v")
            release_url = data.get("html_url", "")
            if not latest or not is_newer_version(latest, APP_VERSION):
                callback(result)
                return

            result = UpdateCheckResult(latest_version=latest, release_url=release_url)
            if can_apply_in_app_update():
                manifest = fetch_manifest_for_tag(tag)
                app_version = str(manifest.get("app_version", ""))
                if app_version and is_newer_version(app_version, APP_VERSION):
                    result = UpdateCheckResult(
                        latest_version=app_version,
                        release_url=release_url,
                        manifest=manifest,
                        in_app_available=True,
                    )
            callback(result)
        except Exception:
            callback(UpdateCheckResult())

    threading.Thread(target=_worker, daemon=True).start()


def _local_manifest(install_root: Path) -> dict[str, Any] | None:
    path = install_root / "manifest.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _should_refresh_runtime(manifest: dict[str, Any], install_root: Path) -> bool:
    local = _local_manifest(install_root)
    if local is None:
        return True
    return str(manifest.get("pyside6_version", "")) != str(local.get("pyside6_version", ""))


def download_and_stage_update(
    manifest: dict[str, Any],
    install_root: Path,
    *,
    progress: ProgressCallback | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> Path:
    windows = manifest.get("windows")
    if not isinstance(windows, dict):
        msg = "Manifest is missing windows section"
        raise ValueError(msg)

    staging = cache_dir() / "staging"
    if staging.exists():
        shutil.rmtree(staging)

    if _should_refresh_runtime(manifest, install_root):
        if should_cancel and should_cancel():
            raise UpdateCancelledError
        wheels = windows.get("pyside6_wheels")
        if not isinstance(wheels, list) or not wheels:
            msg = "Manifest is missing windows.pyside6_wheels"
            raise ValueError(msg)
        install_pyside6_wheels(wheels, runtime_dir(install_root), progress=progress)

    if should_cancel and should_cancel():
        raise UpdateCancelledError

    app_info = windows.get("app")
    if not isinstance(app_info, dict):
        msg = "Manifest is missing windows.app"
        raise ValueError(msg)
    install_app_bundle(app_info, staging, progress=progress)

    pending_manifest = install_root / "manifest.json.pending"
    pending_manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return staging


def launch_update_helper(install_root: Path, staging: Path) -> None:
    helper_name = "update-helper.exe" if sys.platform == "win32" else "update-helper"
    helper = install_root / helper_name
    if not helper.is_file():
        msg = f"Update helper not found at {helper}"
        raise FileNotFoundError(msg)

    cmd = [
        str(helper),
        "--install-root",
        str(install_root),
        "--staging",
        str(staging),
        "--wait-pid",
        str(os.getpid()),
    ]
    subprocess.Popen(cmd, cwd=install_root)


def finalize_pending_manifest(install_root: Path) -> None:
    pending = install_root / "manifest.json.pending"
    if pending.is_file():
        pending.replace(install_root / "manifest.json")
