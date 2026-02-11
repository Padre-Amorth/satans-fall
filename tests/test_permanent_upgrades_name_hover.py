import os
from pathlib import Path

import pygame

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def rightmost_non_bg_x(surf, start_x, y, bg):
    w = surf.get_width()
    rx = start_x
    for x in range(start_x, w):
        if tuple(surf.get_at((x, y))[:3]) != bg:
            rx = x
    # scan to the right looking for the last non-bg pixel in a small region
    last = start_x
    for x in range(start_x, min(w, start_x + 200)):
        if tuple(surf.get_at((x, y))[:3]) != bg:
            last = x
    return last


def test_stat_name_enlarges_on_hover(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    g.show_permanent_upgrades()
    left_x = g.width // 2 - 420

    # Compute expected default and hover widths using the same fonts as UI
    font_medium = pygame.font.Font(None, 24)
    font_name_hover = pygame.font.Font(None, 28)
    default_w = font_medium.render("POWER", True, (255, 68, 68)).get_width()
    hover_w = font_name_hover.render("POWER", True, (255, 68, 68)).get_width()

    # Draw without hover and sample pixel just after default width
    g.mouse_x = 0
    g.mouse_y = 0
    g.ui.draw_permanent_upgrades()
    surf = g.screen
    bg = tuple(surf.get_at((0, 0))[:3])

    sample_x = left_x + default_w + 2
    sample_y = 140 + 15
    before_pixel = tuple(surf.get_at((sample_x, sample_y))[:3])

    # Draw with hover over POWER name and sample same coordinate
    g.show_permanent_upgrades()
    g.mouse_x = left_x + 10
    g.mouse_y = 140 + 10
    g.ui.draw_permanent_upgrades()
    surf2 = g.screen
    after_pixel = tuple(surf2.get_at((sample_x, sample_y))[:3])

    assert before_pixel == bg and after_pixel != bg, "Name does not enlarge on hover (no visual expansion detected)"