"""Swap staged app files into place after the main process exits."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.install_layout import app_current_dir  # noqa: E402
from src.updater import finalize_pending_manifest  # noqa: E402


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)) == 0:
                return False
            return int(exit_code.value) == STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _wait_for_pid(pid: int, timeout_s: float = 120.0) -> None:
    deadline = time.monotonic() + timeout_s
    while _pid_alive(pid):
        if time.monotonic() >= deadline:
            msg = f"Timed out waiting for process {pid} to exit"
            raise TimeoutError(msg)
        time.sleep(0.2)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True, help="Extracted app bundle to promote")
    parser.add_argument("--wait-pid", type=int, required=True)
    return parser.parse_args(argv)


def _swap_app_dir(install_root: Path, staging: Path) -> None:
    current = app_current_dir(install_root)
    old = install_root / "app" / "old"
    if old.exists():
        shutil.rmtree(old)
    current.parent.mkdir(parents=True, exist_ok=True)
    if current.exists():
        current.rename(old)
    staging.rename(current)
    if old.exists():
        shutil.rmtree(old)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _wait_for_pid(args.wait_pid)
    _swap_app_dir(args.install_root, args.staging)
    finalize_pending_manifest(args.install_root)

    launcher = args.install_root / ("launcher.exe" if sys.platform == "win32" else "launcher")
    if launcher.is_file():
        subprocess.Popen([str(launcher)], cwd=args.install_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
