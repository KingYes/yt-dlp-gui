"""Configure import and DLL paths for an external PySide6 runtime."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .install_layout import resolve_install_root, runtime_dir


def find_runtime_dir() -> Path | None:
    env = os.environ.get("YT_DLP_GUI_RUNTIME")
    if env:
        candidate = Path(env)
        if _runtime_has_pyside6(candidate):
            return candidate

    if not getattr(sys, "frozen", False):
        local = Path.cwd() / "runtime"
        if _runtime_has_pyside6(local):
            return local
        return None

    install_root = resolve_install_root()
    if install_root is not None:
        candidate = runtime_dir(install_root)
        if _runtime_has_pyside6(candidate):
            return candidate

    exe_dir = Path(sys.executable).resolve().parent
    for candidate in (exe_dir / "runtime", exe_dir.parent / "runtime", exe_dir.parent.parent / "runtime"):
        if _runtime_has_pyside6(candidate):
            return candidate
    return None


def _runtime_has_pyside6(path: Path) -> bool:
    return (path / "PySide6").is_dir() and (path / "shiboken6").is_dir()


def _add_dll_directory(path: Path) -> None:
    if not path.is_dir():
        return
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(path))
    pyside6 = path / "PySide6"
    if pyside6.is_dir() and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(pyside6))


def configure_split_runtime() -> Path | None:
    runtime = find_runtime_dir()
    if runtime is None:
        return None

    runtime_str = str(runtime)
    if runtime_str not in sys.path:
        sys.path.insert(0, runtime_str)

    if sys.platform == "win32":
        _add_dll_directory(runtime)
        os.environ["PATH"] = runtime_str + os.pathsep + os.environ.get("PATH", "")

    return runtime


def runtime_env(runtime: Path | None) -> dict[str, str]:
    env = os.environ.copy()
    if runtime is None:
        return env
    runtime_str = str(runtime)
    env["YT_DLP_GUI_RUNTIME"] = runtime_str
    if sys.platform == "win32":
        env["PATH"] = runtime_str + os.pathsep + env.get("PATH", "")
    return env
