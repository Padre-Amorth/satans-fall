"""Simple text and font cache to reduce calls to pygame.font.Font and .render

Provides `FontCache.get_font(size, name=None)` and `TextCache.get_text(text, font, color)`
which cache Font objects and rendered Surfaces respectively.
"""

from __future__ import annotations

from typing import Dict, Tuple

import pygame

_font_cache: Dict[Tuple[str | None, int, bool, bool], pygame.font.Font] = {}
_text_cache: Dict[Tuple[str, int, Tuple[int, int, int]], pygame.Surface] = {}


def clear_cache() -> None:
    _font_cache.clear()
    _text_cache.clear()


def get_font(
    size: int = 24, name: str | None = None, bold: bool = False, italic: bool = False
) -> pygame.font.Font:
    # Ensure pygame font module is initialized; if it was shut down during tests,
    # reinitialize and clear caches to avoid returning stale Font objects.
    try:
        if not pygame.font.get_init():
            pygame.font.init()
            clear_cache()
    except Exception:
        # If checking init fails for any reason, attempt to init anyway
        try:
            pygame.font.init()
            clear_cache()
        except Exception:
            pass

    key = (name, size, bold, italic)
    if key in _font_cache:
        return _font_cache[key]
    try:
        if name is None:
            f = pygame.font.Font(None, size)
        else:
            f = pygame.font.SysFont(name, size)
        f.set_bold(bold)
        f.set_italic(italic)
    except Exception:
        # In headless/test envs Font creation might fail; fall back to pygame.font.Font(None, size)
        # Ensure font module is initialized before fallback attempt
        try:
            pygame.font.init()
        except Exception:
            pass
        f = pygame.font.Font(None, size)
    _font_cache[key] = f
    return f


def get_text(
    text: str, font: pygame.font.Font, color: Tuple[int, int, int]
) -> pygame.Surface:
    key = (text, id(font), color)
    if key in _text_cache:
        return _text_cache[key]
    try:
        surf = font.render(text, True, color)
    except Exception:
        # If the underlying font object is invalid (e.g., "font module quit since font created"),
        # attempt to recover by reinitializing the font module, clearing caches and recreating a font.
        clear_cache()
        try:
            pygame.font.init()
        except Exception:
            pass
        # Try to determine a reasonable fallback size from the font if possible
        try:
            size = font.get_height()
        except Exception:
            size = 24
        fallback_font = get_font(size)
        surf = fallback_font.render(text, True, color)
        _text_cache[(text, id(fallback_font), color)] = surf
        return surf

    _text_cache[key] = surf
    return surf


__all__ = ["get_font", "get_text", "clear_cache"]
