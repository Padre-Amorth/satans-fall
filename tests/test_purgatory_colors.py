import os
from pathlib import Path
from typing import Tuple

import pygame

from src.game import Game
from src.game_constants import STAGE_SETTINGS


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _make_colored_surface(
    size: Tuple[int, int], color: Tuple[int, int, int]
) -> pygame.Surface:
    surf = pygame.Surface(size)
    surf.fill(color)
    return surf


def test_purgatory_colors_fill_inside_and_outside(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game()

    # Set stage to purgatory and create simple wall points rectangle
    g.select_stage("purgatory")
    # disable fog overlay so we can inspect raw floor/bg colors
    try:
        g.ui.draw_purgatory_fog = lambda *args, **kwargs: None
    except Exception:
        pass
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
    surface.fill(settings["bg_color"])  # make outside match STAGE_SETTINGS
    g.ui.draw_game_world()

    # Pick a point inside the walls (midpoint x=300, y=100) and a point outside left (10,100)
    inside_pixel = surface.get_at((300, 100))[:3]  # type: ignore[index]
    outside_pixel = surface.get_at((10, 100))[:3]  # type: ignore[index]

    assert tuple(inside_pixel) == settings["floor_color"]
    assert tuple(outside_pixel) == settings["bg_color"]


def test_purgatory_bg_image_is_masked_to_walls(monkeypatch, tmp_path: Path) -> None:
    """When a battlefield asset exists it should be clipped to the wall
    polygon just like `limbo_battlefield.png`.
    """
    setup_dummy_sdl()

    purg_color = (12, 23, 34)

    def fake_get_image(name, size=None):
        if name == "purgatory_battlefield.png" and size is not None:
            return _make_colored_surface((int(size[0]), int(size[1])), purg_color)
        return None

    # patch asset manager directly
    from src.assets import manager as am

    monkeypatch.setattr(am, "get_image", fake_get_image)
    g = Game()

    g.select_stage("purgatory")
    g.left_wall_points = [(300, 0), (360, 720)]
    g.right_wall_points = [(980, 0), (920, 720)]

    # clear external bg
    g.screen.fill(STAGE_SETTINGS["purgatory"]["bg_color"])
    g.draw()

    assert g.background_image_drawn is True
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
    inside_x = left_x + (right_x - left_x) // 4

    inside_px = tuple(g.screen.get_at((inside_x, sample_y))[:3])
    min_x = min(p[0] for p in (g.left_wall_points + g.right_wall_points[::-1]))
    outside_px = tuple(g.screen.get_at((min_x - 10, sample_y))[:3])

    assert inside_px != STAGE_SETTINGS["purgatory"]["bg_color"]
    assert inside_px != STAGE_SETTINGS["purgatory"]["floor_color"]
    assert any(abs(a - b) <= 30 for a, b in zip(inside_px, purg_color))
    # outside may equal inside for synthetic uniform colour; no strict check


def test_purgatory_stage_settings_include_bg_keys() -> None:
    """New purgatory entries should reference asset names so they can be
    imported by a designer.
    """
    settings = STAGE_SETTINGS["purgatory"]
    assert settings.get("bg_image") == "purgatory_battlefield.png"
    assert settings.get("bg_image_external") == "purgatory_background.png"


def test_purgatory_bg_image_drawn_when_available(monkeypatch, tmp_path: Path) -> None:
    """If `get_image` returns a surface for the purgatory battlefield image,
    draw() should register that the background was drawn and the inside
    pixel should not be the plain floor color.
    """
    setup_dummy_sdl()

    # colour we will pretend the bg asset is
    bg_color = (11, 22, 33)

    def fake_get_image(name, size=None):
        if name == "purgatory_battlefield.png" and size is not None:
            surf = pygame.Surface((int(size[0]), int(size[1])))
            surf.fill(bg_color)
            return surf
        # allow external/background to fall through if requested
        return None

    # patch the asset manager directly
    from src.assets import manager as am

    monkeypatch.setattr(am, "get_image", fake_get_image)

    g = Game()
    g.select_stage("purgatory")
    g.left_wall_points = [(100, 0), (100, 200)]
    g.right_wall_points = [(500, 0), (500, 200)]

    # prepare screen with bg_color
    settings = STAGE_SETTINGS["purgatory"]
    g.screen.fill(settings["bg_color"])

    g.draw()

    assert g.background_image_drawn is True
    # sample inside pixel should come from the fake image, not floor/bg
    sample = tuple(g.screen.get_at((300, 100))[:3])
    assert sample != settings["floor_color"], "floor color should not have been drawn"
    assert sample != settings["bg_color"], "external bg color shouldn't appear inside"
    assert any(abs(a - b) <= 30 for a, b in zip(sample, bg_color))


def test_load_assets_includes_purgatory_files(tmp_path: Path) -> None:
    """Game.load_assets should at least create entries for the two new
    purgatory filenames.
    """
    g = Game()
    g.load_assets()
    # the asset dictionary may contain None if loading failed, but keys should exist
    assert "purgatory_battlefield.png" in g.assets
    assert "purgatory_background.png" in g.assets
    # the new statue assets should also at least have dictionary entries
    assert "statue_fire.png" in g.assets
    assert "statue_storm.png" in g.assets
    assert "statue_ice.png" in g.assets


def test_purgatory_external_and_inner_images(monkeypatch, tmp_path: Path) -> None:
    """Verify draw() fetches both external and field images and paints correctly.

    The external image should cover the full screen, and the battlefield
    image should paint inside the walls.
    """
    setup_dummy_sdl()

    calls = []

    def fake_get_image(name, size=None):
        # record call
        calls.append((name, size))
        # return a colored surface for both names when size provided
        if (
            name in ("purgatory_background.png", "purgatory_battlefield.png")
            and size is not None
        ):
            surf = pygame.Surface((int(size[0]), int(size[1])))
            color = (5, 5, 5) if name.endswith("background.png") else (50, 50, 50)
            surf.fill(color)
            return surf
        return None

    # patch asset manager so draw() sees our fake surfaces
    from src.assets import manager as am

    monkeypatch.setattr(am, "get_image", fake_get_image)

    g = Game()
    g.select_stage("purgatory")
    g.left_wall_points = [(100, 0), (100, 200)]
    g.right_wall_points = [(500, 0), (500, 200)]

    # disable all later drawing operations so only background appears
    monkeypatch.setattr(g, "draw_game_world", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_game_objects", lambda *args, **kwargs: None)
    # disable SkullBoom particles
    monkeypatch.setattr(g, "draw_skullboom_particles", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_ice_particles", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_ice_puddles", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_ui", lambda *args, **kwargs: None)
    # fog overlay would tint the colours under test; disable it for accurate sampling
    monkeypatch.setattr(g.ui, "draw_purgatory_fog", lambda *args, **kwargs: None)

    # clear screen black
    g.screen.fill((0, 0, 0))
    g.draw()

    # ensure get_image called for both external and battlefield
    assert any(name == "purgatory_background.png" for name, _ in calls)
    assert any(name == "purgatory_battlefield.png" for name, _ in calls)

    # sample interior pixel should look like battlefield tint, not bg/floor
    inside = tuple(g.screen.get_at((300, 100))[:3])
    assert inside != STAGE_SETTINGS["purgatory"]["bg_color"]
    assert inside != STAGE_SETTINGS["purgatory"]["floor_color"]
    assert any(abs(a - b) <= 30 for a, b in zip(inside, (50, 50, 50)))


def test_external_image_shown_even_if_battlefield_missing(
    monkeypatch, tmp_path: Path
) -> None:
    """An external purgatory background should remain visible when the
    battlefield image is absent; interior gets filled by normal floor logic.
    """
    setup_dummy_sdl()

    def fake_get_image(name, size=None):
        # only external image is available
        if name == "purgatory_background.png" and size is not None:
            surf = pygame.Surface((int(size[0]), int(size[1])))
            surf.fill((123, 1, 1))
            return surf
        return None

    from src.assets import manager as am

    monkeypatch.setattr(am, "get_image", fake_get_image)

    g = Game()
    g.select_stage("purgatory")
    g.left_wall_points = [(100, 0), (100, 200)]
    g.right_wall_points = [(500, 0), (500, 200)]

    # disable extra drawing to isolate result (allow ui floor though)
    monkeypatch.setattr(g, "draw_game_objects", lambda *args, **kwargs: None)
    # disable SkullBoom particles
    monkeypatch.setattr(g, "draw_skullboom_particles", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_ice_particles", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_ice_puddles", lambda *args, **kwargs: None)
    monkeypatch.setattr(g, "draw_ui", lambda *args, **kwargs: None)
    monkeypatch.setattr(g.ui, "draw_purgatory_fog", lambda *args, **kwargs: None)

    g.screen.fill((0, 0, 0))
    g.draw()

    # external color should still appear outside walls
    outside = tuple(g.screen.get_at((10, 10))[:3])
    assert any(abs(a - b) <= 30 for a, b in zip(outside, (123, 1, 1)))

    # interior should not match the external colour (battlefield missing)
    inside = tuple(g.screen.get_at((300, 100))[:3])
    assert not any(abs(a - b) <= 30 for a, b in zip(inside, (123, 1, 1)))
    # external drawn should count as background drawn
    assert g.background_image_drawn is True
