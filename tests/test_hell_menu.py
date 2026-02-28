import os
from pathlib import Path

import pygame

from src.game import Game
from src.game_constants import STAGE_SETTINGS


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_stage_settings_contains_hell():
    assert "hell" in STAGE_SETTINGS
    assert "hell_2" in STAGE_SETTINGS
    assert "hell_3" in STAGE_SETTINGS


def test_hell_menu_open_and_selects(tmp_path: Path):
    setup_dummy_sdl()
    g = Game()

    # Navigate to stage selection screen
    g.showing_main_menu = False
    g.showing_stage_menu = True
    # HELL button geometry matches draw_stage_menu (btn_w=280, btn_h=46, spacing=58, base_y=h//2-100, i=3)
    hell_rect = pygame.Rect(g.width // 2 - 140, g.height // 2 + 74, 280, 46)
    center = hell_rect.center

    # Click to open submenu
    g.handle_mouse_click(center, button=1)
    assert g.showing_hell_menu is True

    # Now click on first hell option
    option_w = 320
    option_h = 48
    start_x = g.width // 2 - option_w // 2
    start_y = g.height // 2 - 40
    hell1_rect = pygame.Rect(start_x, start_y, option_w, option_h)
    g.handle_mouse_click(hell1_rect.center, button=1)
    assert g.selected_stage == "hell"
    assert g.showing_hell_menu is False


def test_escape_closes_hell_menu(tmp_path: Path):
    setup_dummy_sdl()
    g = Game()
    g.showing_main_menu = False
    g.showing_stage_menu = True
    g.showing_hell_menu = True

    # send ESC key
    g.handle_keydown(pygame.K_ESCAPE)
    assert g.showing_hell_menu is False
