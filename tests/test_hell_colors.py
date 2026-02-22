import os
from pathlib import Path

from src.game import Game
from src.game_constants import STAGE_SETTINGS


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_hell_colors_fill_inside_and_outside(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Set stage to hell and create simple wall points rectangle
    g.select_stage("hell")
    # Simple vertical walls at x=100 and x=500
    g.left_wall_points = [(100, 0), (100, 200)]
    g.right_wall_points = [(500, 0), (500, 200)]

    # Ensure stage settings indicate dark red background, dark gray floor and
    # dark gray walls (wall color unified across stages)
    settings = STAGE_SETTINGS["hell"]
    assert settings["bg_color"] == (80, 8, 8)
    assert settings["floor_color"] == (60, 60, 60)
    assert settings["wall_color"] == (40, 40, 40)

    # Draw world and inspect pixels
    surface = g.screen
    # Ensure canvas is cleared as draw_game_world uses screen provided by Game
    surface.fill(settings["bg_color"])  # make outside match STAGE_SETTINGS
    g.ui.draw_game_world()

    # Pick a point inside the walls (midpoint x=300, y=100) and a point outside left (10,100)
    inside_pixel = surface.get_at((300, 100))[:3]  # type: ignore[index]
    outside_pixel = surface.get_at((10, 100))[:3]  # type: ignore[index]
    # Sample a pixel on the left wall (well inside the rendered wall region for HELL)
    wall_pixel = surface.get_at((60, 100))[:3]  # type: ignore[index]
    # Check thin black borders: outer (at x=50) and inner (at x=100)
    outer_border = surface.get_at((50, 100))[:3]  # type: ignore[index]
    inner_border = surface.get_at((100, 100))[:3]  # type: ignore[index]

    # colors may be quantized by the dummy driver, allow small tolerance
    def close(c1, c2, tol=25):
        # allow up to ~25-point deviation per channel, which covers the
        # aggressive color quantization we see under the dummy driver
        return all(abs(a - b) <= tol for a, b in zip(c1, c2))

    assert close(tuple(inside_pixel), settings["floor_color"])
    assert close(tuple(outside_pixel), settings["bg_color"])
    assert close(tuple(wall_pixel), settings["wall_color"])
    assert close(tuple(outer_border), (0, 0, 0))
    assert close(tuple(inner_border), (0, 0, 0))
