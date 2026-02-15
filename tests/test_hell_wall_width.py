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


def test_hell_has_wider_base_than_purgatory(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    g.select_stage("purgatory")
    purg_top, purg_bot = get_top_bottom_widths(g)

    g.select_stage("hell")
    hell_top, hell_bot = get_top_bottom_widths(g)

    # HELL walls are vertical but slightly narrower: top==bottom and 100px narrower than Purgatory's top
    assert (
        hell_top == hell_bot
    ), f"HELL walls should be vertical (top={hell_top} bot={hell_bot})"
    assert (
        hell_top == purg_top - 100
    ), f"HELL top should be 100px narrower than Purgatory top (hell={hell_top} purg_top={purg_top})"
    assert (
        hell_bot > purg_bot
    ), f"HELL bottom width should still be wider than Purgatory bottom (hell={hell_bot} purg={purg_bot})"
