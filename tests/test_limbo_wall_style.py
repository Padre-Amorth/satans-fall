import os
from pathlib import Path

from src.game import Game
from src.game_constants import STAGE_SETTINGS, WALL_THICKNESS


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_limbo_walls_thicker_and_warmer(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game()

    # Use a simple vertical wall so sampling is deterministic
    left_x = 320
    right_x = 960

    g.select_stage("limbo")
    g.left_wall_points = [(left_x, 0), (left_x, g.height)]
    g.right_wall_points = [(right_x, 0), (right_x, g.height)]

    # Clear canvas to external bg
    g.screen.fill(STAGE_SETTINGS["limbo"]["bg_color"])

    # Draw only game world
    g.ui.draw_game_world()

    # Expected (we implemented a +4 px increase for Limbo)
    expected_thickness = WALL_THICKNESS + 4
    expected_color = STAGE_SETTINGS["limbo"]["wall_color"]

    # Sample a pixel guaranteed to be inside the left wall polygon
    sample_y = 100
    wall_sample_x = left_x - (expected_thickness // 2)
    wall_px = tuple(g.screen.get_at((wall_sample_x, sample_y))[:3])

    assert wall_px == expected_color

    # Pixel well outside the wall should NOT match the wall color
    outside_px = tuple(
        g.screen.get_at((left_x - expected_thickness - 10, sample_y))[:3]
    )
    assert outside_px != expected_color
