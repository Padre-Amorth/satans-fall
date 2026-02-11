import os
from pathlib import Path

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def get_top_bottom_widths(game: Game):
    game.generate_walls()
    left_top_x = game.left_wall_points[0][0]
    right_top_x = game.right_wall_points[0][0]
    left_bot_x = game.left_wall_points[-1][0]
    right_bot_x = game.right_wall_points[-1][0]
    top_width = right_top_x - left_top_x
    bot_width = right_bot_x - left_bot_x
    return top_width, bot_width


def test_purgatory_wider_than_limbo(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    g.select_stage("limbo")
    limbo_top, limbo_bot = get_top_bottom_widths(g)

    g.select_stage("purgatory")
    purg_top, purg_bot = get_top_bottom_widths(g)

    assert purg_top > limbo_top, f"Purgatory top width should be wider than Limbo (purg={purg_top} limbo={limbo_top})"
    assert purg_bot > limbo_bot, f"Purgatory bottom width should be wider than Limbo (purg={purg_bot} limbo={limbo_bot})"