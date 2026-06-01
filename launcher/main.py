"""Launch the installed yt-dlp-gui app with an external PySide6 runtime."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.install_layout import app_exe_path, resolve_install_root  # noqa: E402
from src.pyside6_installer import ensure_runtime, resolve_install_root_for_cli  # noqa: E402
from src.runtime_paths import configure_split_runtime, find_runtime_dir, runtime_env  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, help="Override install root detection")
    return parser.parse_known_args(argv)


def _install_runtime_helper(install_root: Path) -> Path:
    helper = install_root / ("install-runtime.exe" if sys.platform == "win32" else "install-runtime")
    if not helper.is_file():
        helper = _ROOT / "install-runtime" / "main.py"
        if helper.is_file():
            return helper
        msg = f"install-runtime helper not found under {install_root}"
        raise FileNotFoundError(msg)
    return helper


def _run_install_runtime(helper: Path, install_root: Path, manifest: Path) -> subprocess.CompletedProcess[bytes]:
    cmd = [str(helper), "--manifest", str(manifest), "--dest", str(install_root), "--runtime-only"]
    if helper.suffix == ".py":
        cmd = [sys.executable, *cmd]
    return subprocess.run(cmd, check=False)


def main(argv: list[str] | None = None) -> int:
    args, app_argv = _parse_args(argv)
    install_root = args.install_root or resolve_install_root() or resolve_install_root_for_cli()

    runtime = find_runtime_dir()
    if runtime is None or not (runtime / "PySide6").is_dir():
        helper = _install_runtime_helper(install_root)
        manifest = install_root / "manifest.json"
        if not manifest.is_file():
            print(f"Error: missing runtime and manifest at {manifest}", file=sys.stderr)
            return 1
        result = _run_install_runtime(helper, install_root, manifest)
        if result.returncode != 0:
            return result.returncode
        ensure_runtime(install_root)

    app_exe = app_exe_path(install_root)
    if not app_exe.is_file():
        print(f"Error: app executable not found at {app_exe}", file=sys.stderr)
        return 1

    runtime = configure_split_runtime() or find_runtime_dir()
    env = runtime_env(runtime)
    completed = subprocess.run([str(app_exe), *app_argv], env=env, cwd=app_exe.parent, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
