"""yt-dlp GUI entry point."""

import sys


def main() -> None:
    if getattr(sys, "_yt_dlp_gui_running", False):
        return
    sys._yt_dlp_gui_running = True  # type: ignore[attr-defined]

    from src.qt.app import run_qt_app

    run_qt_app()


if __name__ == "__main__":
    main()
