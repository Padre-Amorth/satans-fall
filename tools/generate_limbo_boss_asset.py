"""Utility to create a placeholder limbo boss sprite.

Run this script from the project root to drop a simple 120x120 PNG into
`assets/boss_limbo.png`.  The game will then load the image instead of
falling back to the vector/ellipse drawing.

Usage:
    python tools/generate_limbo_boss_asset.py

If you prefer to supply your own artwork, simply replace the generated file
with your custom sprite (keeping the same name).
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main():
    root = Path(__file__).resolve().parents[1]
    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    out = assets / "boss_limbo.png"

    # create a simple purple square with "LIMBO" text
    size = (120, 120)
    im = Image.new("RGBA", size, (150, 0, 150, 255))
    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        font = None
    text = "LIMBO"
    w, h = draw.textsize(text, font=font)
    draw.text(
        ((size[0] - w) / 2, (size[1] - h) / 2),
        text,
        fill=(255, 255, 255, 255),
        font=font,
    )
    im.save(out)
    print(f"Generated placeholder asset at {out}")


if __name__ == "__main__":
    main()
