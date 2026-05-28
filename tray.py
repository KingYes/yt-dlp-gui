from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from typing import Any

from PIL import Image, ImageDraw, ImageFont

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
    """Cross-platform system tray icon using pystray."""

    def __init__(
        self,
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._on_show = on_show
        self._on_quit = on_quit
        self._icon: Any = None
        self._thread: threading.Thread | None = None
        self._tooltip = "yt-dlp GUI"

    @property
    def available(self) -> bool:
        return _HAS_PYSTRAY

    def start(self) -> None:
        if not _HAS_PYSTRAY or self._icon is not None:
            return

        menu = pystray.Menu(
            pystray.MenuItem("Show Window", self._show_action, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit_action),
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
        if self._icon is not None:
            with contextlib.suppress(Exception):
                self._icon.stop()
            self._icon = None
            self._thread = None

    def update_tooltip(self, text: str) -> None:
        self._tooltip = text
        if self._icon is not None:
            self._icon.title = text

    def notify(self, title: str, message: str) -> None:
        if self._icon is not None:
            with contextlib.suppress(Exception):
                self._icon.notify(message, title)

    def _show_action(self, icon: object, item: object) -> None:
        self._on_show()

    def _quit_action(self, icon: object, item: object) -> None:
        self._on_quit()
