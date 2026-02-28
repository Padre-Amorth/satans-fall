import os
from pathlib import Path

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_ui_draw_hud_runs(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game()

    # set some state
    g.score = 123
    g.wave = 2
    g.time_elapsed = 125
    g.player.health = 30
    g.player.max_health = 50
    g.player_xp = 4
    g.xp_to_next_level = 10

    # ensure calling UI HUD does not raise
    g.ui.draw_hud()


def test_game_draw_hud_delegates_to_ui(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game()

    called = {"v": False}

    def fake_draw_hud(shake_x=0, shake_y=0):
        called["v"] = True

    g.ui.draw_hud = fake_draw_hud  # type: ignore[method-assign]
    g.draw_hud()
    assert called["v"] is True


def test_game_draw_center_messages_delegates(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game()

    called = {"v": False}

    def fake_draw_center(shake_x=0, shake_y=0):
        called["v"] = True

    g.ui.draw_center_messages = fake_draw_center  # type: ignore[method-assign]
    g.draw_center_messages()
    assert called["v"] is True
