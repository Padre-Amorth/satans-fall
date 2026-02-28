import logging
import os
from pathlib import Path

import pygame

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_purgatory_drawn_on_click_and_logs(tmp_path: Path, caplog):
    setup_dummy_sdl()
    caplog.set_level(logging.DEBUG)
    g = Game()

    # Navigate to stage selection and click the purgatory button
    g.showing_main_menu = False
    g.showing_stage_menu = True
    # Purgatory button geometry matches draw_stage_menu (btn_w=280, btn_h=46, spacing=58, base_y=h//2-100, i=2)
    purg_rect = pygame.Rect(g.width // 2 - 140, g.height // 2 + 16, 280, 46)
    g.handle_mouse_click(purg_rect.center, button=1)

    # The flag should be set
    assert g.showing_purgatory_menu is True

    # Call draw_stage_menu to trigger the drawing branch
    g.draw_stage_menu()

    # The last drawn menu should be recorded and logs should contain debug message
    assert getattr(g, "_last_drawn_menu", None) == "purgatory"
    assert any("Purgatory" in r.message for r in caplog.records)
