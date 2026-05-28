from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from i18n import t

try:
    import pystray

    _HAS_PYSTRAY = True
except Exception:
    pystray = None  # type: ignore[assignment]
    _HAS_PYSTRAY = False


def _create_icon_image(size: int = 64) -> Image.Image:
    """Generate a simple 'YT' icon with Pillow."""
    img = Image.new("RGBA", (size, size), (220, 53, 69, 255))
    draw = ImageDraw.Draw(img)
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    try:
        font = ImageFont.truetype("arial.ttf", size // 2)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "YT", font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2
    y = (size - text_h) // 2 - bbox[1]
    draw.text((x, y), "YT", fill="white", font=font)
    return img


class TrayManager:
    """Cross-platform system tray icon using pystray.

    pystray callbacks run on a background thread.  On macOS with recent
    Python / Tk builds, **any** Tkinter call (including ``widget.after()``)
    from a non-main thread triggers a fatal ``EXC_BREAKPOINT``.  We avoid
    this by setting ``threading.Event`` flags from the callbacks and letting
    the owner poll them with a Tk ``after`` timer on the main thread.
    """

    def __init__(
        self,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._on_show = on_show
        self._on_quit = on_quit
        self._icon: Any = None
        self._thread: threading.Thread | None = None
        self._tooltip = t("tray.tooltip")
        self._show_event = threading.Event()
        self._quit_event = threading.Event()

    @property
    def available(self) -> bool:
        return _HAS_PYSTRAY

    def start(self) -> None:
        if not _HAS_PYSTRAY or self._icon is not None:
            return

        menu = pystray.Menu(
            pystray.MenuItem(t("tray.show_window"), self._show_action, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray.quit"), self._quit_action),
        )

        self._icon = pystray.Icon(
            name="yt-dlp-gui",
            icon=_create_icon_image(),
            title=self._tooltip,
            menu=menu,
        )

        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Mark the tray as stopped.

        On macOS, ``pystray.Icon.stop()`` tears down the ``NSStatusItem``
        via AppKit calls that must run on the AppKit thread.  Calling it
        from the main (Tk) thread crashes with ``EXC_BREAKPOINT``.  Since
        the tray thread is a daemon thread it will be cleaned up
        automatically when the process exits, so we simply drop our
        reference.
        """
        self._icon = None
        self._thread = None

    def poll_events(self) -> None:
        """Check pending tray events. Must be called from the main thread."""
        if self._show_event.is_set():
            self._show_event.clear()
            self._on_show()
        if self._quit_event.is_set():
            self._quit_event.clear()
            self._on_quit()

    def update_tooltip(self, text: str) -> None:
        self._tooltip = text
        if self._icon is not None:
            self._icon.title = text

    def notify(self, title: str, message: str) -> None:
        if self._icon is not None:
            with contextlib.suppress(Exception):
                self._icon.notify(message, title)

    def _show_action(self, icon: object, item: object) -> None:
        self._show_event.set()

    def _quit_action(self, icon: object, item: object) -> None:
        self._quit_event.set()
