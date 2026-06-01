"""CLI helper to download PySide6 wheels and/or the app bundle from a manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.install_layout import default_install_root  # noqa: E402
from src.pyside6_installer import install_from_manifest, load_manifest  # noqa: E402


def _progress(phase: str, current: int, total: int) -> None:
    if phase == "download" and total > 0:
        percent = min(100, int(current * 100 / total))
        print(f"download {percent}%", flush=True)
    elif phase == "wheel" and total > 0:
        print(f"wheel {current}/{total}", flush=True)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Path or URL to update-manifest.json")
    parser.add_argument("--dest", type=Path, help="Install root (defaults to LOCALAPPDATA\\Programs\\yt-dlp-gui on Windows)")
    parser.add_argument("--runtime-only", action="store_true", help="Install only PySide6 wheels")
    parser.add_argument("--app-only", action="store_true", help="Install only the app bundle")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.runtime_only and args.app_only:
        print("Error: --runtime-only and --app-only are mutually exclusive", file=sys.stderr)
        return 1

    install_root = args.dest
    if install_root is None:
        if sys.platform != "win32":
            print("Error: --dest is required on non-Windows platforms", file=sys.stderr)
            return 1
        install_root = default_install_root()

    manifest = load_manifest(args.manifest)
    install_from_manifest(
        manifest,
        install_root,
        install_runtime=not args.app_only,
        install_app=not args.runtime_only,
        progress=_progress,
    )
    print(f"Installed to {install_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
