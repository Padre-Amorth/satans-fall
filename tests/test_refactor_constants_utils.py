import os
from pathlib import Path

from src.game import Game
from src.game_constants import (
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_PLAYER_ANIM_SPEED,
    DEFAULT_WAVE_DURATION,
    DEFAULT_WIDTH,
    STAGE_SETTINGS,
    WALL_THICKNESS,
)


def setup_dummy_sdl():
    # Ensure headless SDL for CI/test environments
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_game_uses_default_constants(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game()

    assert g.width == DEFAULT_WIDTH
    assert g.height == DEFAULT_HEIGHT
    assert g.fps == DEFAULT_FPS
    assert g.player_anim_speed == DEFAULT_PLAYER_ANIM_SPEED
    assert g.wave_duration == DEFAULT_WAVE_DURATION
    assert g.stage_settings == STAGE_SETTINGS


def test_clamp_to_walls_respects_wall_thickness(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game()
    g.left_wall_points = [(100, 0)]
    g.right_wall_points = [(500, 0)]

    left_boundary = 100 + WALL_THICKNESS
    right_boundary = 500 - WALL_THICKNESS

    assert g.clamp_to_walls(50) == left_boundary
    assert g.clamp_to_walls(600) == right_boundary
    assert g.clamp_to_walls(300) == 300
