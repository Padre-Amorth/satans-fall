"""Test suite for updated statue projectile offsets (Limbo tuning: 10px inward, 50px downward)."""

import pygame

from src import game_constants
from src.core.entities.tower import Tower
from src.game import Game
from src.systems.weapon_system import statue_projectile_offsets


def test_limbo_statue_projectile_offset_x_is_60px():
    """Limbo statue projectiles should spawn 60px toward the center (10px increase from 50)."""
    assert game_constants.STATUE_PROJECTILE_OFFSET_X_LIMBO == 60


def test_statue_projectile_offset_y_is_60px():
    """All statue projectiles should spawn 60px downward (50px increase from 10)."""
    assert game_constants.STATUE_PROJECTILE_OFFSET_Y == 60


def test_limbo_statue_fires_at_correct_offset():
    """Fire tower in Limbo should create projectile at offset-adjusted position."""
    pygame.init()

    tower = Tower(320, 400, tower_type="fire")

    # Create a dummy enemy
    class DummyEnemy:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    enemy = DummyEnemy(500, 300)
    proj = tower.fire_at_closest([enemy], origin_x=320 + 60, origin_y=400 + 60)

    assert proj is not None
    # Projectile should spawn at origin_x, origin_y
    assert proj.x == 320 + 60
    assert proj.y == 400 + 60


def test_limbo_stage_offset_calculation():
    """Helper function should return (60, 60) for Limbo stages."""
    pygame.init()
    g = Game(debug=True)

    limbo_stages = ["limbo", "limbo_2", "limbo_3"]

    for stage in limbo_stages:
        g.selected_stage = stage
        x, y = statue_projectile_offsets(g)
        assert x == 60, f"Expected X=60 for {stage}, got {x}"
        assert y == 60, f"Expected Y=60 for {stage}, got {y}"


def test_limbo_final_offset_calculation():
    """limbo_final should subtract 35 from X (60-35=25), keep Y at 60."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo_final"

    x, y = statue_projectile_offsets(g)
    expected_x = 60 - 35  # = 25
    expected_y = 60

    assert x == expected_x, f"Expected X={expected_x} for limbo_final, got {x}"
    assert y == expected_y, f"Expected Y={expected_y} for limbo_final, got {y}"


def test_purgatory_and_hell_unchanged():
    """Purgatory and Hell should keep their offsets (10px X, 60px Y)."""
    pygame.init()
    g = Game(debug=True)

    for stage, expected_x in [("purgatory", 10), ("hell", 10)]:
        g.selected_stage = stage
        x, y = statue_projectile_offsets(g)
        assert x == expected_x, f"Expected X={expected_x} for {stage}, got {x}"
        assert y == 10, f"Expected Y=10 for {stage}, got {y}"


def test_ice_tower_limbo_fires_at_offset():
    """Ice tower in Limbo with offset should spawn projectile correctly."""
    pygame.init()

    tower = Tower(320, 400, tower_type="ice")

    class DummyEnemy:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    enemy = DummyEnemy(500, 300)
    proj = tower.fire_at_closest([enemy], origin_x=320 + 60, origin_y=400 + 60)

    assert proj is not None
    assert proj.x == 380  # 320 + 60
    assert proj.y == 460  # 400 + 60
    assert proj.appearance == "ice_statue"


def test_storm_tower_limbo_fires_at_offset():
    """Storm tower in Limbo with offset should spawn projectile correctly."""
    pygame.init()

    tower = Tower(320, 400, tower_type="storm")

    class DummyEnemy:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    enemy = DummyEnemy(500, 300)
    proj = tower.fire_at_closest([enemy], origin_x=320 + 60, origin_y=400 + 60)

    assert proj is not None
    assert proj.x == 380  # 320 + 60
    assert proj.y == 460  # 400 + 60
    assert proj.appearance == "storm_statue"
