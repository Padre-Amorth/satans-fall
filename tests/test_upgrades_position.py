import os
from pathlib import Path

import pygame

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_upgrades_button_is_at_bottom_and_clickable(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    g.show_stage_menu()

    upgrades_rect = pygame.Rect(g.width // 2 - 125, max(20, g.height - 80), 250, 35)
    # Click center of upgrades rect
    g.handle_mouse_click(upgrades_rect.center, button=1)

    assert g.showing_permanent_upgrades is True
