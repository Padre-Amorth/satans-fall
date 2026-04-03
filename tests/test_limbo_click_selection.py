import os
from pathlib import Path

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_click_first_limbo_selects_limbo(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game()

    # Open limbo submenu directly (stage selection screen must be active)
    g.showing_main_menu = False
    g.showing_stage_menu = True
    g.showing_limbo_menu = True

    # Compute limbo1 rect as in code (matches input_handler limbo submenu layout)
    option_w = 320
    option_h = 48
    start_x = g.width // 2 - option_w // 2
    start_y = g.height // 2 - 40
    spacing = 60

    # Click near center of LIMBO 1
    click_pos = (start_x + option_w // 2, start_y + option_h // 2)
    g.handle_mouse_click(click_pos, button=1)

    assert g.selected_stage == "limbo"
    assert not g.showing_limbo_menu

    # Test LIMBO FINAL (index 3, at start_y + spacing*3)
    g.showing_main_menu = False
    g.showing_stage_menu = True
    g.showing_limbo_menu = True
    click_pos = (start_x + option_w // 2, start_y + spacing * 3 + option_h // 2)
    g.handle_mouse_click(click_pos, button=1)
    assert g.selected_stage == "limbo_final"
    assert not g.showing_limbo_menu

    # Test BACK button (at start_y + spacing*4 + 10)
    g.showing_main_menu = False
    g.showing_stage_menu = True
    g.showing_limbo_menu = True
    back_x = g.width // 2
    back_y = start_y + spacing * 4 + 10 + 16  # center of 32px tall back button
    g.handle_mouse_click((back_x, back_y), button=1)
    assert not g.showing_limbo_menu
    assert g.showing_stage_menu
