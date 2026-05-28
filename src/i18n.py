"""Lightweight JSON-based internationalization module.

Loads flat key-value translation files from the ``locales/`` directory.
English (``en.json``) is always loaded as the fallback so partial
translations still produce usable UI text.
"""

import json
import sys
from pathlib import Path
from typing import Any

_LOCALES_DIR: Path
if getattr(sys, "frozen", False):
    _LOCALES_DIR = Path(sys.executable).parent / "locales"
else:
    _LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"

_fallback: dict[str, str] = {}
_strings: dict[str, str] = {}
_current_language: str = "en"
_current_direction: str = "ltr"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError):
        return {}


def load_language(code: str) -> None:
    """Load a language by its ISO code, falling back to English for missing keys."""
    global _fallback, _strings, _current_language, _current_direction

    en_path = _LOCALES_DIR / "en.json"
    _fallback = {k: v for k, v in _load_json(en_path).items() if not k.startswith("_")}

    if code == "en":
        _strings = _fallback
        _current_direction = "ltr"
    else:
        lang_path = _LOCALES_DIR / f"{code}.json"
        raw = _load_json(lang_path)
        meta = raw.get("_meta", {})
        _current_direction = meta.get("direction", "ltr")
        merged = dict(_fallback)
        for k, v in raw.items():
            if not k.startswith("_") and isinstance(v, str) and not v.startswith("[TODO]"):
                merged[k] = v
        _strings = merged

    _current_language = code


def set_language(code: str) -> None:
    """Switch the active language at runtime."""
    load_language(code)


def t(key: str, **kwargs: Any) -> str:
    """Look up a translation key and interpolate any ``{placeholder}`` values."""
    value = _strings.get(key) or _fallback.get(key) or key
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            return value
    return value


def current_language() -> str:
    """Return the ISO code of the currently loaded language."""
    return _current_language


def is_rtl() -> bool:
    """Return True if the current language direction is right-to-left."""
    return _current_direction == "rtl"


def get_available_languages() -> list[tuple[str, str]]:
    """Scan the locales directory and return ``(code, display_name)`` pairs.

    Each JSON file must contain a ``_meta`` object with a ``name`` field.
    Results are sorted alphabetically by display name.
    """
    languages: list[tuple[str, str]] = []
    if not _LOCALES_DIR.is_dir():
        return [("en", "English")]
    for path in sorted(_LOCALES_DIR.glob("*.json")):
        data = _load_json(path)
        meta = data.get("_meta", {})
        name = meta.get("name", path.stem)
        code = meta.get("code", path.stem)
        languages.append((code, name))
    if not languages:
        return [("en", "English")]
    return sorted(languages, key=lambda x: x[1])
