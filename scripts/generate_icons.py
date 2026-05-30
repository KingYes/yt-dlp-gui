"""Generate application icons for Windows/macOS/Linux builds."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

_ROOT = Path(__file__).resolve().parent.parent
_ASSETS = _ROOT / "assets"


def _draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = max(2, size // 8)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=size // 6,
        fill=(66, 133, 244, 255),
    )
    tri_w = size // 3
    cx = size // 2 + size // 16
    cy = size // 2
    draw.polygon(
        [
            (cx - tri_w // 2, cy - tri_w // 2),
            (cx - tri_w // 2, cy + tri_w // 2),
            (cx + tri_w // 2, cy),
        ],
        fill=(255, 255, 255, 255),
    )
    return img


def main() -> None:
    _ASSETS.mkdir(parents=True, exist_ok=True)
    base = _draw_icon(256)
    base.save(_ASSETS / "icon.png")
    base.save(_ASSETS / "icon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    print(f"Wrote {_ASSETS / 'icon.png'} and {_ASSETS / 'icon.ico'}")


if __name__ == "__main__":
    main()
