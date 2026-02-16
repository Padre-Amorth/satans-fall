import os
from pathlib import Path

import pygame

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_permanent_upgrades_show_effect_text_and_alignment(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Give some levels to stats so effect text and bar fill are shown
    g.permanent_stats["power"] = 3
    g.permanent_stats["vigor"] = 1

    g.show_permanent_upgrades()
    g.ui.draw_permanent_upgrades()

    surf = g.screen
    left_x = g.width // 2 - 420

    # Check that effect text for power appears around expected area (left_x + 340)
    eff_x = left_x + 340
    eff_y = 140 + 15 + (12 // 2)
    bg = tuple(surf.get_at((0, 0))[:3])

    found_effect = False
    for dx in range(-4, 5):
        for dy in range(-2, 3):
            x = max(0, min(surf.get_width() - 1, eff_x + dx))
            y = max(0, min(surf.get_height() - 1, eff_y + dy))
            if tuple(surf.get_at((x, y))[:3]) != bg:
                found_effect = True
                break
        if found_effect:
            break

    assert found_effect, "Effect text for stat not rendered"

    # Check bar alignment: compute name width and expected bar_x per UI logic
    font_medium = pygame.font.Font(None, 24)
    names = ["POWER", "VIGOR", "ADRENALINE", "STRUCTURE"]
    max_name_w = max(
        font_medium.render(n, True, (255, 255, 255)).get_width() for n in names
    )
    expected_bar_x = left_x + max(120, max_name_w + 24)

    # Compute expected fill width for the current level and sample a pixel just after the filled area
    bar_width = 180  # matches UI implementation
    fill_width = min(bar_width, (g.permanent_stats["power"] / 10) * bar_width)
    sample_x = expected_bar_x + int(fill_width) + 2
    sample_y = 140 + 15
    sample_pixel = tuple(surf.get_at((sample_x, sample_y))[:3])
    # Accept either the bar background or the border color as valid evidence of alignment
    assert sample_pixel in (
        (8, 8, 8),
        (68, 68, 68),
    ), f"Bar not aligned at expected x {expected_bar_x}, found pixel {sample_pixel}"
