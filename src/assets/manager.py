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
    """Load original image and cache it (may be None on failure).

    To support hot-reloading in tests, we allow a previously-failed lookup
    to be retried if the file appears later on disk.  The cache stores None
    for a missing file, but we only return that cached None immediately if
    the path still does not exist.  Otherwise we clear the cache entry and
    try loading again.
    """
    path = os.path.join(_ASSETS_DIR, name)
    # Try case-insensitive match if file missing (handles Tenebrae.PNG etc).
    if not os.path.exists(path):
        try:
            for fname in os.listdir(_ASSETS_DIR):
                if fname.lower() == name.lower():
                    path = os.path.join(_ASSETS_DIR, fname)
                    break
        except (AttributeError, TypeError, ValueError, KeyError):
            pass

    if name in _original_cache:
        cached = _original_cache[name]
        if cached is None:
            # if the file now exists on disk, remove the stale cache entry
            # so that the subsequent load attempt will actually try again
            if os.path.exists(path):
                del _original_cache[name]
            else:
                return None
        else:
            return cached

    try:
        loaded = pygame.image.load(path)
        try:
            # convert_alpha may fail in headless environments; fall back to raw surface
            surf = loaded.convert_alpha()
        except (AttributeError, TypeError, ValueError, KeyError):
            surf = loaded
        _original_cache[name] = surf
    except Exception as e:
        # cache None so we don't repeatedly log the same missing-file warnings
        _original_cache[name] = None
    return _original_cache[name]


def get_image(
    name: str, size: Optional[Tuple[int, int]] = None
) -> Optional[pygame.Surface]:
    """Get an image by name, optionally scaled to `size` (w, h).

    Returned Surface is cached; callers should .copy() if they plan to modify it.
    The cache will automatically retry loading if the file appears after an
    earlier failure (see :func:`_load_original`).
    """
    key = (name, size)

    # If we have a cached scaled result but it was None (previous failure),
    # check whether the file exists now and purge the stale entry to force a
    # reload.
    if key in _scaled_cache:
        cached = _scaled_cache[key]
        if cached is None:
            path = os.path.join(_ASSETS_DIR, name)
            if os.path.exists(path):
                # clear both caches so the new file will be loaded below
                del _scaled_cache[key]
                if name in _original_cache:
                    del _original_cache[name]
            else:
                return None
        else:
            return cached

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
        _scaled_cache[key] = orig
        return orig


def preload_images(names: list[str]) -> None:
    """Preload original images for the given names into the cache."""
    for n in names:
        _load_original(n)


__all__ = ["get_image", "clear_cache", "preload_images"]
