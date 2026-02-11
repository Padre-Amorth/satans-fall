import os
from pathlib import Path

import pygame

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_stat_hover_highlights_bar_border(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Hover over POWER name
    g.show_permanent_upgrades()
    left_x = g.width // 2 - 420
    g.mouse_x = left_x + 10
    g.mouse_y = 140 + 10

    g.ui.draw_permanent_upgrades()
    surf = g.screen

    # Bar border should be gold when hovered
    font_medium = pygame.font.Font(None, 24)
    names = ["POWER", "VIGOR", "ADRENALINE", "STRUCTURE"]
    max_name_w = max(font_medium.render(n, True, (255, 255, 255)).get_width() for n in names)
    expected_bar_x = left_x + max(120, max_name_w + 24)
    sample_x = expected_bar_x + 1
    sample_y = 140 + 15
    sample_pixel = tuple(surf.get_at((sample_x, sample_y))[:3])
    assert sample_pixel == (255, 224, 20), f"Expected gold border on hover, found {sample_pixel}"


def test_skill_tree_box_hover_highlight_and_tooltip(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Hover over first FIRE left box
    g.show_permanent_upgrades()
    left_x = g.width // 2 - 420
    separator_y = 320
    tree_top_y = separator_y - 150
    tree_box_w = 50
    tree_col_spacing = 120
    tree_base_x = left_x + 680
    col_x = tree_base_x
    inner_col_offset = tree_box_w // 2 + 1
    left_col_x = col_x - inner_col_offset
    y = tree_top_y

    g.mouse_x = left_col_x
    g.mouse_y = y

    g.ui.draw_permanent_upgrades()
    surf = g.screen

    # Top-left corner of left rect should show gold border after hover
    sample_pixel = tuple(surf.get_at((left_col_x, y))[:3])
    assert sample_pixel == (255, 224, 20), f"Expected gold border on skill box hover, found {sample_pixel}"

    # And tooltip area should not be background (i.e., tooltip rendered)
    tip_x = col_x
    tip_y = tree_top_y + 3 * 46 + 36 + 12
    bg = tuple(surf.get_at((0, 0))[:3])
    found = False
    for dx in range(-3, 4):
        for dy in range(-2, 3):
            px = max(0, min(surf.get_width() - 1, tip_x + dx))
            py = max(0, min(surf.get_height() - 1, tip_y + dy))
            if tuple(surf.get_at((px, py))[:3]) != bg:
                found = True
                break
        if found:
            break
    assert found, "Tooltip not rendered on skill hover"