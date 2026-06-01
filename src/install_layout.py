"""Installed app directory layout (Windows split runtime + app bundles)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_INSTALL_DIR_NAME = "yt-dlp-gui"
_RUNTIME_DIR_NAME = "runtime"
_APP_DIR_NAME = "app"
_CURRENT_APP_DIR_NAME = "current"
_MANIFEST_FILE_NAME = "manifest.json"


def resolve_install_root(start: Path | None = None) -> Path | None:
    """Return the install root if *start* is inside the installed layout."""
    if start is None:
        if getattr(sys, "frozen", False):
            start = Path(sys.executable).resolve()
        else:
            return None

    current = start.resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if _looks_like_install_root(candidate):
            return candidate
    return None


def _looks_like_install_root(path: Path) -> bool:
    if (path / _MANIFEST_FILE_NAME).is_file():
        return True
    return (path / _RUNTIME_DIR_NAME).is_dir() and (path / _APP_DIR_NAME).is_dir()


def runtime_dir(install_root: Path) -> Path:
    return install_root / _RUNTIME_DIR_NAME


def app_current_dir(install_root: Path) -> Path:
    return install_root / _APP_DIR_NAME / _CURRENT_APP_DIR_NAME


def app_exe_name() -> str:
    return "yt-dlp-gui.exe" if sys.platform == "win32" else "yt-dlp-gui"


def app_exe_path(install_root: Path) -> Path:
    return app_current_dir(install_root) / app_exe_name()


def installed_data_dir(install_root: Path | None = None) -> Path | None:
    """Per-user data directory for an installed Windows layout."""
    if sys.platform != "win32":
        return None
    root = install_root or resolve_install_root()
    if root is None:
        return None
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / _INSTALL_DIR_NAME


def default_install_root() -> Path:
    """Default per-user install location on Windows."""
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        msg = "LOCALAPPDATA is not set"
        raise OSError(msg)
    return Path(local_appdata) / "Programs" / _INSTALL_DIR_NAME


def cache_dir() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA", str(Path.home()))
    return Path(local_appdata) / _INSTALL_DIR_NAME / "cache"
