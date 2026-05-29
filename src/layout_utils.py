"""RTL-aware layout helpers for grid-based CustomTkinter UIs."""

from .i18n import is_rtl


def _anchor_start() -> str:
    """Return 'e' for RTL languages, 'w' for LTR."""
    return "e" if is_rtl() else "w"


def _sticky_start() -> str:
    """Return 'e' for RTL languages, 'w' for LTR."""
    return "e" if is_rtl() else "w"


def _sticky_end() -> str:
    """Return 'w' for RTL languages, 'e' for LTR."""
    return "w" if is_rtl() else "e"


def _pad_start(outer: int = 0, inner: int = 0) -> tuple[int, int]:
    """Return (left, right) padding -- ``outer`` on the start side, ``inner`` on end."""
    return (inner, outer) if is_rtl() else (outer, inner)


def _pad_end(outer: int = 0, inner: int = 0) -> tuple[int, int]:
    """Return (left, right) padding -- ``outer`` on the end side, ``inner`` on start."""
    return (outer, inner) if is_rtl() else (inner, outer)


def _c(col: int, max_col: int) -> int:
    """Mirror a grid column index for RTL layouts."""
    return max_col - col if is_rtl() else col


def _justify() -> str:
    """Return 'right' for RTL languages, 'left' for LTR."""
    return "right" if is_rtl() else "left"


def _padx(start: int, end: int) -> tuple[int, int]:
    """Return ``(left, right)`` padding, swapping for RTL."""
    return (end, start) if is_rtl() else (start, end)
