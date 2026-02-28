import os
from pathlib import Path

import pygame

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_upgrades_button_is_at_bottom_and_clickable(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game()

    # Game starts on main menu — permanent upgrades button is on the main menu
    assert g.showing_main_menu is True

    # Upgrades button geometry matches draw_main_menu (up_w=250, up_h=36, y=h//2+55)
    upgrades_rect = pygame.Rect(g.width // 2 - 125, g.height // 2 + 55, 250, 36)
    # Click center of upgrades rect
    g.handle_mouse_click(upgrades_rect.center, button=1)

    assert g.showing_permanent_upgrades is True
