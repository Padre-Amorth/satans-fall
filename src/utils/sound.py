"""Procedural sound synthesis utilities.

This module provides helpers to generate simple sounds at runtime using
`numpy`.  It is intentionally lightweight and avoids any external asset
files; the resulting :class:`pygame.mixer.Sound` objects can be played immediately.

The generated sound buffers are cached by parameter tuple to avoid repeated
numpy calculations when the same tone is requested multiple times.  Tests
exercise the primary API and verify the returned objects look sane.
"""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np
import pygame

# simple cache keyed by descriptive id and volume (used by soft click)
_sound_cache: Dict[Tuple[str, float], pygame.mixer.Sound] = {}


def suono_click_soft(volume: float = 0.2) -> pygame.mixer.Sound:
    """Generate a soft, noisy click suitable for menu interactions.

    The implementation is taken verbatim from the user's snippet: 40 ms of
    uniform noise shaped with a quartic envelope.  The timbre is noisy and
    soft compared to a pure tone.
    """
    sample_rate = 44100
    durata = 0.04
    samples = int(sample_rate * durata)

    # ensure mixer initialised
    if not pygame.mixer.get_init():
        try:
            pygame.mixer.init(frequency=sample_rate, size=-16, channels=1)
        except Exception:
            return pygame.mixer.Sound(buffer=b"")

    # simple cache
    cache_key = ("soft", volume)
    if cache_key in _sound_cache:
        return _sound_cache[cache_key]

    rumore = np.random.uniform(-1, 1, samples)
    envelope = np.linspace(1, 0, samples) ** 4
    onda = volume * rumore * envelope * 0.3

    audio = np.int16(onda * 32767)
    mixer_init = pygame.mixer.get_init()
    if mixer_init is not None and mixer_init[2] == 2:
        audio = np.column_stack((audio, audio))
    try:
        snd = pygame.mixer.Sound(buffer=audio.tobytes())
    except Exception:
        snd = pygame.mixer.Sound(buffer=b"")

    _sound_cache[cache_key] = snd
    return snd


def play_click_variato() -> None:
    """Play a menu click using the soft-click generator.

    The original design allowed the frequency to vary; the current
    implementation simply delegates to :func:`suono_click_soft`.  The
    frequency variable is no longer used but retained here as a comment
    placeholder for future variation logic.
    """
    # freq = np.random.randint(550, 650)  # currently unused
    try:
        suono_click_soft().play()
    except Exception:
        pass
