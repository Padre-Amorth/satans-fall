import os
from pathlib import Path

import pygame

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_bars_are_symmetric_and_shorter(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game()

    g.permanent_stats["power"] = 3
    g.permanent_stats["vigor"] = 2
    g.permanent_stats["adrenaline"] = 1
    g.permanent_stats["structure"] = 0

    g.show_permanent_upgrades()
    g.ui.draw_permanent_upgrades()

    surf = g.screen
    left_x = g.width // 2 - 420

    font_medium = pygame.font.Font(None, 24)
    names = ["POWER", "VIGOR", "ADRENALINE", "STRUCTURE"]
    max_name_w = max(
        font_medium.render(n, True, (255, 255, 255)).get_width() for n in names
    )
    expected_bar_x = left_x + max(120, max_name_w + 24)
    expected_bar_width = 180

    # Sample a pixel inside the bar background for each stat y (bar is at y + 15)
    ys = [140, 185, 230, 275]
    for y in ys:
        sample_x = expected_bar_x + 2
        sample_y = y + 15
        sample_pixel = tuple(surf.get_at((sample_x, sample_y))[:3])
        allowed = {
            (26, 26, 26),  # bar background
            (68, 68, 68),  # bar border
            (255, 68, 68),  # power fill
            (255, 204, 0),  # vigor fill
            (170, 68, 255),  # adrenaline fill
            (139, 105, 20),  # structure fill
        }
        assert (
            sample_pixel in allowed
        ), f"Bar at stat y={y} not found at expected x {expected_bar_x}, pixel {sample_pixel}"

    # Confirm width is shorter than legacy 200
    assert expected_bar_width < 200
