import os
from pathlib import Path

import pygame

from src.game import Game
from src.game_constants import STAGE_SETTINGS


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_purgatory_colors_fill_inside_and_outside(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Set stage to purgatory and create simple wall points rectangle
    g.select_stage("purgatory")
    # Simple vertical walls at x=100 and x=500
    g.left_wall_points = [(100, 0), (100, 200)]
    g.right_wall_points = [(500, 0), (500, 200)]

    # Ensure stage settings indicate black background and dark gray floor
    settings = STAGE_SETTINGS["purgatory"]
    assert settings["bg_color"] == (0, 0, 0)
    assert settings["floor_color"] == (40, 40, 40)

    # Draw world and inspect pixels
    surface = g.screen
    # Ensure canvas is cleared as draw_game_world uses screen provided by Game
    g.ui.draw_game_world()

    # Pick a point inside the walls (midpoint x=300, y=100) and a point outside left (50,100)
    inside_pixel = surface.get_at((300, 100))[:3]
    outside_pixel = surface.get_at((50, 100))[:3]

    assert tuple(inside_pixel) == settings["floor_color"]
    assert tuple(outside_pixel) == settings["bg_color"]
