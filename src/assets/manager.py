import logging
import os
from typing import Dict, Optional, Tuple

import pygame

logger = logging.getLogger(__name__)

# Assets directory (project root /assets)
_ASSETS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "assets")
)

# Caches: original images and scaled variants
_original_cache: Dict[str, Optional[pygame.Surface]] = {}
_scaled_cache: Dict[Tuple[str, Optional[Tuple[int, int]]], Optional[pygame.Surface]] = (
    {}
)


def clear_cache() -> None:
    """Clear all cached images (useful for tests)."""
    _original_cache.clear()
    _scaled_cache.clear()


def _load_original(name: str) -> Optional[pygame.Surface]:
    """Load original image and cache it (may be None on failure)."""
    if name in _original_cache:
        return _original_cache[name]

    path = os.path.join(_ASSETS_DIR, name)
    try:
        loaded = pygame.image.load(path)
        try:
            # convert_alpha may fail in headless environments; fall back to raw surface
            surf = loaded.convert_alpha()
        except Exception:
            surf = loaded
        _original_cache[name] = surf
    except Exception as e:
        logger.warning("Asset %s could not be loaded: %s", path, e)
        _original_cache[name] = None
    return _original_cache[name]


def get_image(
    name: str, size: Optional[Tuple[int, int]] = None
) -> Optional[pygame.Surface]:
    """Get an image by name, optionally scaled to `size` (w, h).

    Returned Surface is cached; callers should .copy() if they plan to modify it.
    """
    key = (name, size)
    if key in _scaled_cache:
        return _scaled_cache[key]

    orig = _load_original(name)
    if orig is None:
        _scaled_cache[key] = None
        return None

    if size is None:
        _scaled_cache[key] = orig
        return orig

    try:
        surf = pygame.transform.smoothscale(orig, size)
        _scaled_cache[key] = surf
        return surf
    except Exception as e:
        logger.warning("Failed to scale %s to %s: %s", name, size, e)
        _scaled_cache[key] = orig
        return orig


def preload_images(names: list[str]) -> None:
    """Preload original images for the given names into the cache."""
    for n in names:
        _load_original(n)


__all__ = ["get_image", "clear_cache", "preload_images"]
