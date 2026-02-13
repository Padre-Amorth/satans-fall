import os
from pathlib import Path

import pygame

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_click_first_limbo_selects_limbo(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Show stage menu and open limbo submenu
    g.show_stage_menu()
    g.showing_limbo_menu = True

    # Compute limbo1 rect as in code
    option_w = 320
    option_h = 48
    start_x = g.width // 2 - option_w // 2
    start_y = g.height // 2 - 40

    # Click near center of LIMBO 1
    click_pos = (start_x + option_w // 2, start_y + option_h // 2)
    g.handle_mouse_click(click_pos, button=1)

    assert g.selected_stage == "limbo"
    assert not g.showing_limbo_menu
