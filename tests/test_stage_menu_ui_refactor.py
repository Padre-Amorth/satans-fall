import os
from pathlib import Path

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_ui_draw_stage_menu_main_and_submenus(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Draw main stage menu
    g.show_stage_menu()
    g.ui.draw_stage_menu()
    assert getattr(g, "_last_drawn_menu", None) == "stage_main"

    # Show limbo submenu and draw
    g.show_stage_menu()
    g.showing_limbo_menu = True
    g.ui.draw_stage_menu()
    assert getattr(g, "_last_drawn_menu", None) == "limbo"

    # Show purgatory submenu and draw
    g.show_stage_menu()
    g.showing_limbo_menu = False
    g.showing_purgatory_menu = True
    g.ui.draw_stage_menu()
    assert getattr(g, "_last_drawn_menu", None) == "purgatory"


def test_game_draw_stage_menu_delegates(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    called = {"v": False}

    def fake_draw(shake_x=0, shake_y=0):
        called["v"] = True

    g.ui.draw_stage_menu = fake_draw  # type: ignore[method-assign]
    g.draw_stage_menu()
    assert called["v"] is True
