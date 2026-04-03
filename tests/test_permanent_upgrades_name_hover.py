import os
from pathlib import Path

import pygame

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def rightmost_non_bg_x(surf, start_x, y, bg):
    w = surf.get_width()
    for x in range(start_x, w):
        if tuple(surf.get_at((x, y))[:3]) != bg:
            last = x
    # scan to the right looking for the last non-bg pixel in a small region
    last = start_x
    for x in range(start_x, min(w, start_x + 200)):
        if tuple(surf.get_at((x, y))[:3]) != bg:
            last = x
    return last


def test_stat_name_enlarges_on_hover(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game()

    g.show_permanent_upgrades()
    left_x = g.width // 2 - 420

    # Compute expected default and hover widths using the same fonts as UI
    font_medium = pygame.font.Font(None, 24)
    font_name_hover = pygame.font.Font(None, 26)
    default_w = font_medium.render("POWER", True, (255, 68, 68)).get_width()
    hover_w = font_name_hover.render("POWER", True, (255, 68, 68)).get_width()

    # Draw without hover and capture baseline non-bg pixels in the area to the right
    g.mouse_x = 0
    g.mouse_y = 0
    g.ui.draw_permanent_upgrades()
    surf = g.screen
    bg = tuple(surf.get_at((0, 0))[:3])

    hover_w = font_name_hover.render("POWER", True, (255, 68, 68)).get_width()
    search_x0 = left_x + default_w + 1
    search_x1 = left_x + default_w + hover_w + 4
    search_y0 = 140
    search_y1 = 140 + 30

    baseline_non_bg = set()
    for x in range(search_x0, min(surf.get_width(), search_x1 + 1)):
        for y in range(search_y0, min(surf.get_height(), search_y1 + 1)):
            if tuple(surf.get_at((x, y))[:3]) != bg:
                baseline_non_bg.add((x, y))

    # Draw with hover over POWER name and look for any new non-bg pixel in same area
    g.show_permanent_upgrades()
    g.mouse_x = left_x + 10
    g.mouse_y = 140 + 10
    g.ui.draw_permanent_upgrades()
    surf2 = g.screen

    found_new = False
    for x in range(search_x0, min(surf2.get_width(), search_x1 + 1)):
        for y in range(search_y0, min(surf2.get_height(), search_y1 + 1)):
            if tuple(surf2.get_at((x, y))[:3]) != bg and (x, y) not in baseline_non_bg:
                found_new = True
                break
        if found_new:
            break

    assert found_new, "Name does not enlarge on hover (no visual expansion detected)"
