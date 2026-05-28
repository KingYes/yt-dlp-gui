import threading
from collections.abc import Callable

import requests

_GITHUB_REPO = "KingYes/yt-dlp-gui"
_RELEASES_URL = f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest"
_TIMEOUT = 10

APP_VERSION = "0.0.1"


def check_for_update(callback: Callable[[str | None, str | None], None]) -> None:
    """Check GitHub for a newer release in a background thread.

    callback(latest_version, download_url) is called on the main thread.
    Both args are None if up-to-date or on error.
    """

    def _worker() -> None:
        try:
            resp = requests.get(_RELEASES_URL, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            tag = data.get("tag_name", "").lstrip("v")
            if tag and tag != APP_VERSION:
                url = data.get("html_url", "")
                callback(tag, url)
            else:
                callback(None, None)
        except Exception:
            callback(None, None)

    threading.Thread(target=_worker, daemon=True).start()
