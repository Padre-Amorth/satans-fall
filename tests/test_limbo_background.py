import os
from typing import Tuple

import pygame

from src.game import Game
from src.game_constants import STAGE_SETTINGS


def setup_dummy_sdl() -> None:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _make_colored_surface(
    size: Tuple[int, int], color: Tuple[int, int, int]
) -> pygame.Surface:
    surf = pygame.Surface(size)
    surf.fill(color)
    return surf


def test_limbo_bg_image_is_masked_to_walls(
    monkeypatch, tmp_path: "pathlib.Path"
) -> None:
    """When `limbo_battlefield.png` is provided, it should be masked to the inside polygon
    (same behavior as `prologo`) so the image follows oblique/irregular walls.
    """
    setup_dummy_sdl()

    # Patch get_image to return a uniform-colored Surface for the limbo battlefield
    limbo_color = (12, 34, 56)

    def fake_get_image(name, size=None):
        if name == "limbo_battlefield.png" and size is not None:
            return _make_colored_surface((int(size[0]), int(size[1])), limbo_color)
        return None

    # Patch the get_image name used by Game.draw() (imported in src.game)
    monkeypatch.setattr("src.game.get_image", fake_get_image)
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Configure an oblique (slanted) pair of walls so the interior polygon is non-rectangular
    g.select_stage("limbo")
    g.left_wall_points = [(300, 0), (360, 720)]  # slanted inwards as y increases
    g.right_wall_points = [(980, 0), (920, 720)]

    # Clear screen first to the external bg color
    g.screen.fill(STAGE_SETTINGS["limbo"]["bg_color"])

    # Draw full frame (this will call get_image for the limbo bg)
    g.draw()

    # Game must have drawn the battlefield image (masked) instead of the solid floor fill
    assert g.background_image_drawn is True

    # Pick a sample y and compute an x guaranteed to be inside the polygon (linear interp)
    sample_y = 200
    progress = sample_y / g.height
    left_x = int(
        g.left_wall_points[0][0]
        + (g.left_wall_points[1][0] - g.left_wall_points[0][0]) * progress
    )
    right_x = int(
        g.right_wall_points[0][0]
        + (g.right_wall_points[1][0] - g.right_wall_points[0][0]) * progress
    )
    # Use a point nearer the left wall to avoid UI/HUD overlays near center
    inside_x = left_x + (right_x - left_x) // 4

    inside_px = tuple(g.screen.get_at((inside_x, sample_y))[:3])
    # Choose a pixel just left of the battlefield bbox to verify clipping
    min_x = min(p[0] for p in (g.left_wall_points + g.right_wall_points[::-1]))
    outside_px = tuple(g.screen.get_at((min_x - 10, sample_y))[:3])

    # Inside pixel should NOT be the external bg nor the default limbo floor
    assert inside_px != STAGE_SETTINGS["limbo"]["bg_color"]
    assert inside_px != STAGE_SETTINGS["limbo"]["floor_color"]
    # And it should be visibly close to the color we used for the test image
    assert any(abs(a - b) <= 30 for a, b in zip(inside_px, limbo_color))

    # Pixel immediately outside the polygon must not match the interior (masked) image
    assert inside_px != outside_px
