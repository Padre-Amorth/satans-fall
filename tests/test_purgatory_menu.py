import os
from pathlib import Path

import pygame

from src.game import Game
from src.game_constants import STAGE_SETTINGS


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_stage_settings_contains_purgatory():
    assert "purgatory" in STAGE_SETTINGS
    assert "purgatory_2" in STAGE_SETTINGS
    assert "purgatory_3" in STAGE_SETTINGS


def test_purgatory_menu_open_and_selects(tmp_path: Path):
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Show stage menu and simulate click on Purgatory main button
    g.show_stage_menu()
    # Compute purgatory_rect center used by UI (must match drawing code)
    purg_rect = pygame.Rect(g.width // 2 - 100, g.height // 2 + 70, 200, 40)
    center = purg_rect.center

    # Click to open submenu
    g.handle_mouse_click(center, button=1)
    assert g.showing_purgatory_menu is True

    # Now click on first purgatory option
    option_w = 320
    option_h = 48
    start_x = g.width // 2 - option_w // 2
    start_y = g.height // 2 - 40
    purg1_rect = pygame.Rect(start_x, start_y, option_w, option_h)
    g.handle_mouse_click(purg1_rect.center, button=1)
    assert g.selected_stage == "purgatory"
    assert g.showing_purgatory_menu is False


def test_escape_closes_purgatory_menu(tmp_path: Path):
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))
    g.show_stage_menu()
    g.showing_purgatory_menu = True

    # send ESC key
    g.handle_keydown(pygame.K_ESCAPE)
    assert g.showing_purgatory_menu is False
