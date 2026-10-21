#!/usr/bin/env python3
"""Generate home-assistant/brands images from a source Ferroli logo.

Usage:
    python tools/make_brand_assets.py path/to/ferroli-logo.png [out_dir]

Produces, in <out_dir> (default ./brand_assets):
    icon.png        256x256   (square, transparent, trimmed + padded)
    icon@2x.png     512x512
    logo.png        <=256 tall (wordmark, transparent, trimmed)
    logo@2x.png     <=512 tall

Then copy them into home-assistant/brands under
custom_integrations/ferroli_connect/ and open a PR.
Requires Pillow.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def trim(img: Image.Image) -> Image.Image:
    """Crop away fully transparent borders."""
    img = img.convert("RGBA")
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def make_logo(src: Image.Image, height: int) -> Image.Image:
    w, h = src.size
    new_w = max(1, round(w * height / h))
    return src.resize((new_w, height), Image.LANCZOS)


def make_icon(src: Image.Image, size: int) -> Image.Image:
    """Square canvas with the logo centered, ~10% padding."""
    inner = int(size * 0.8)
    w, h = src.size
    scale = min(inner / w, inner / h)
    resized = src.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(
        resized,
        ((size - resized.width) // 2, (size - resized.height) // 2),
        resized,
    )
    return canvas


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    src_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("brand_assets")
    out_dir.mkdir(parents=True, exist_ok=True)

    src = trim(Image.open(src_path))

    make_icon(src, 256).save(out_dir / "icon.png")
    make_icon(src, 512).save(out_dir / "icon@2x.png")
    make_logo(src, 256).save(out_dir / "logo.png")
    make_logo(src, 512).save(out_dir / "logo@2x.png")

    print(f"Wrote icon.png, icon@2x.png, logo.png, logo@2x.png to {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
