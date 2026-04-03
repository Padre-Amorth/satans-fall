"""Utility for creating weapon icon PNGs from their projectile visuals.

Run this script from the project root; it will iterate over every weapon defined
in ``src/weapons.py``, spawn a temporary ``Projectile`` of the appropriate type,
draw it, scale the resulting surface to ``WEAPON_ICON_SIZE`` and save it into
``assets/weapon_<id>.png`` (lowercased).

This makes it trivial to bootstrap a set of icons that match the in‑game
projectile art without doing any manual drawing.  If you later tweak the
projectile rendering the icons can be regenerated with a single command.

Usage::

    python scripts/generate_weapon_icons.py

Note
----
* SDL uses a display for surface operations; the script sets ``SDL_VIDEODRIVER=dummy``
  so it will work on headless machines or within CI.
* Existing files will be overwritten silently.
"""

import os
import sys

# ensure imports work when invoked from root
sys.path.insert(0, os.path.abspath("."))

import pygame

from src.projectile import Projectile
from src.weapons import WEAPON_DEFS
from src.game_constants import WEAPON_ICON_SIZE


def make_icon_for_weapon(wid: str, output_dir: str) -> None:
    """Create and save icon for weapon ``wid``."""
    # spawn a projectile with a representative radius; smaller weapons get
    # smaller radii so the icon doesn't look overly chunky.
    radius = 12
    try:
        p = Projectile(0, 0, 0, 0, damage=0, radius=radius, weapon_type=wid)
        surf = p.image
    except Exception:
        # fallback: create a simple circle to avoid crashing
        surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 255, 255), (radius, radius), radius)

    icon = pygame.transform.smoothscale(surf, (WEAPON_ICON_SIZE, WEAPON_ICON_SIZE))

    # determine output filename.  use explicit WEAPON_DEFS icon if provided;
    # otherwise fall back to the conventional lowercase pattern used historically.
    d = WEAPON_DEFS.get(wid, {})
    fname = d.get("icon") or f"weapon_{wid.lower()}.png"
    outpath = os.path.join(output_dir, fname)
    try:
        pygame.image.save(icon, outpath)
        print(f"generated {outpath}")
    except Exception as e:
        print(f"failed to save icon for {wid}: {e}")


def main():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    output_dir = os.path.join(os.getcwd(), "assets")
    os.makedirs(output_dir, exist_ok=True)
    for wid in WEAPON_DEFS.keys():
        make_icon_for_weapon(wid, output_dir)
    pygame.quit()


if __name__ == "__main__":
    main()
