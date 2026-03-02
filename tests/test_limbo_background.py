import os
import pathlib
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

    # Patch the asset manager's get_image function directly
    from src.assets import manager as am

    monkeypatch.setattr(am, "get_image", fake_get_image)
    g = Game()

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


def test_limbo_stage_settings_include_bg_keys() -> None:
    """STAGE_SETTINGS entries should expose both battlefield and external names."""
    settings = STAGE_SETTINGS["limbo"]
    assert settings.get("bg_image") == "limbo_battlefield.png"
    assert settings.get("bg_image_external") == "limbo_background.png"


def test_limbo_external_and_inner_images(monkeypatch, tmp_path: "pathlib.Path") -> None:
    """Draw should fetch and paint both external and battlefield surfaces.

    External image fills screen; battlefield image is masked inside walls.
    """
    setup_dummy_sdl()

    calls = []

    def fake_get_image(name, size=None):
        calls.append((name, size))
        if name in ("limbo_background.png", "limbo_battlefield.png") and size is not None:
            surf = pygame.Surface((int(size[0]), int(size[1])))
            color = (5, 5, 5) if name.endswith("background.png") else (50, 50, 50)
            surf.fill(color)
            return surf
        return None

    # patch asset manager so draw() pulls from our fake
    from src.assets import manager as am
    monkeypatch.setattr(am, "get_image", fake_get_image)

    g = Game()
    g.select_stage("limbo")
    g.left_wall_points = [(100, 0), (100, 200)]
    g.right_wall_points = [(500, 0), (500, 200)]

    # prevent any other drawing so we only inspect the background
    monkeypatch.setattr(g, "draw_game_world", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_game_objects", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_skullboom_particles", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_ice_particles", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_ice_puddles", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_ui", lambda *args, **kwargs: None)

    g.screen.fill((0, 0, 0))
    g.draw()

    assert any(name == "limbo_background.png" for name, _ in calls)
    assert any(name == "limbo_battlefield.png" for name, _ in calls)

    inside = tuple(g.screen.get_at((300, 100))[:3])
    outside = tuple(g.screen.get_at((10, 10))[:3])
    # interior should roughly match battlefield color and not be bg/floor
    assert inside != STAGE_SETTINGS["limbo"]["bg_color"]
    assert inside != STAGE_SETTINGS["limbo"]["floor_color"]
    assert any(abs(a - b) <= 30 for a, b in zip(inside, (50, 50, 50)))
    # outside should roughly match our external color
    assert any(abs(a - b) <= 30 for a, b in zip(outside, (5, 5, 5)))


def test_limbo_external_shown_even_if_battlefield_missing(
    monkeypatch, tmp_path: "pathlib.Path"
) -> None:
    """External background should still show when battlefield is absent."""
    setup_dummy_sdl()

    def fake_get_image(name, size=None):
        if name == "limbo_background.png" and size is not None:
            surf = pygame.Surface((int(size[0]), int(size[1])))
            surf.fill((123, 1, 1))
            return surf
        return None

    from src.assets import manager as am
    monkeypatch.setattr(am, "get_image", fake_get_image)

    g = Game()
    g.select_stage("limbo")
    g.left_wall_points = [(100, 0), (100, 200)]
    g.right_wall_points = [(500, 0), (500, 200)]

    monkeypatch.setattr(g, "draw_game_objects", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_skullboom_particles", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_ice_particles", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_ice_puddles", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_ui", lambda *args, **kwargs: None)

    g.screen.fill((0, 0, 0))
    g.draw()

    outside = tuple(g.screen.get_at((10, 10))[:3])
    # outside colour should be close to our fake external image
    assert any(abs(a - b) <= 30 for a, b in zip(outside, (123, 1, 1)))
    # we only care that external background is visible; interior may
    # still show the same colour depending on implementation.
    assert g.background_image_drawn is True


def test_load_assets_includes_limbo_files(tmp_path: "pathlib.Path") -> None:
    """Game.load_assets should create keys for limbo background names."""
    g = Game()
    g.load_assets()
    assert "limbo_battlefield.png" in g.assets
    assert "limbo_background.png" in g.assets
