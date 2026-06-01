"""yt-dlp GUI entry point."""

import sys


def _launch_gui() -> None:
    from src.qt.app import run_qt_app

    run_qt_app()


def main() -> None:
    if getattr(sys, "_yt_dlp_gui_running", False):
        return
    sys._yt_dlp_gui_running = True  # type: ignore[attr-defined]

    _launch_gui()


if __name__ == "__main__":
    main()
