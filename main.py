import sys


def main() -> None:
    if getattr(sys, "_yt_dlp_gui_running", False):
        return
    sys._yt_dlp_gui_running = True  # type: ignore[attr-defined]

    from app import App

    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
