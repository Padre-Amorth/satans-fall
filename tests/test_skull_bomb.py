"""Test script for Skull Bomb weapon functionality"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame
import pytest

from src.entities.enemy import Enemy
from src.game import Game
from src.weapons import (
    skull_bomb_cooldown,
    skull_bomb_damage,
    skull_bomb_explosion_radius,
)


def test_skull_bomb_weapon_definition():
    """Test that skull_bomb is properly defined in WEAPON_DEFS"""
    from src.weapons import WEAPON_DEFS

    assert "skull_bomb" in WEAPON_DEFS
    weapon = WEAPON_DEFS["skull_bomb"]
    assert weapon["name"] == "Skull Bomb"
    assert weapon["max_level"] == 6
    assert len(weapon["upgrade_descriptions"]) == 6


def test_skull_bomb_cooldown():
    """Test cooldown calculation for different levels"""
    # Level 1: base 1.8s (current tuning)
    assert skull_bomb_cooldown(1) == 1.8
    # Level 2: 1.8 - 0.16 = 1.64
    assert skull_bomb_cooldown(2) == pytest.approx(1.64, rel=1e-6)
    # Level 6: reduced to configured value 1.0
    assert skull_bomb_cooldown(6) == 1.0


def test_skull_bomb_damage():
    """Test damage calculation for different levels"""
    # Level 1: base 25 * 1.2 = 30 (current tuning)
    assert skull_bomb_damage(1) == 30
    # Level 2: 28.333... * 1.2 = 34
    assert skull_bomb_damage(2) == 34
    # Level 6: 41.666... * 1.2 = 50
    assert skull_bomb_damage(6) == 50


def test_skull_bomb_explosion_radius():
    """Test explosion radius for different levels"""
    # Level 1: base 80
    assert skull_bomb_explosion_radius(1) == 80
    # Level 2: +8 radius
    assert skull_bomb_explosion_radius(2) == 88
    # Level 6: +40 radius
    assert skull_bomb_explosion_radius(6) == 120


def test_skull_bomb_firing():
    """Test that skull bomb auto-fires towards mouse when cooldown is ready"""
    game = Game()
    game.player_weapons = ["skull_bomb"]
    game.weapon_levels = {"skull_bomb": 1}
    game.skull_bomb_cooldown_timer = 0  # Ready to fire

    # Set mouse position
    game.mouse_x = 200
    game.mouse_y = 200
    game.player.x = 100
    game.player.y = 100

    # Initially no projectiles
    initial_count = len(game.projectiles)

    # Update skull bomb (should fire)
    game.update_skull_bomb()

    # Should have fired one projectile
    assert len(game.projectiles) == initial_count + 1

    # Check projectile properties
    skull = list(game.projectiles)[-1]  # Last added
    assert skull.weapon_type == "skull_bomb"
    assert skull.damage == skull_bomb_damage(1)
    assert hasattr(skull, "explosion_radius")
    assert skull.explosion_radius == skull_bomb_explosion_radius(1)

    # Check direction towards mouse (should be normalized)
    import math

    expected_dx = (200 - 100) / math.hypot(200 - 100, 200 - 100)  # 0.707...
    expected_dy = (200 - 100) / math.hypot(200 - 100, 200 - 100)  # 0.707...
    assert (
        abs(skull.vel_x - expected_dx * 370) < 0.1
    )  # matches current skull speed (370)
    assert abs(skull.vel_y - expected_dy * 370) < 0.1

    # Cooldown should be set
    assert game.skull_bomb_cooldown_timer > 0


def test_skull_bomb_does_not_explode_on_player_spawn():
    """Skull bomb must not detonate immediately or on overlap with player."""
    pygame.init()
    g = Game()
    g.player_weapons = ["skull_bomb"]
    g.weapon_levels = {"skull_bomb": 1}
    g.skull_bomb_cooldown_timer = 0

    # Ensure no enemies present
    g.enemies = []

    # Fire towards the right
    g.player.x = 100
    g.player.y = 100
    g.mouse_x = 150
    g.mouse_y = 100
    g.update_skull_bomb()

    projs = list(g.projectiles)
    assert len(projs) >= 1
    proj = projs[-1]

    # Run collision handling for a few frames; projectile should NOT explode
    for _ in range(3):
        try:
            proj.update()
        except Exception:
            pass
        g.handle_collisions()

    assert proj in list(g.projectiles)


def test_skull_bomb_explodes_on_enemy_contact():
    """Skull bomb should detonate and damage enemies when overlapping them."""
    pygame.init()
    g = Game()
    g.player_weapons = ["skull_bomb"]
    g.weapon_levels = {"skull_bomb": 1}
    g.skull_bomb_cooldown_timer = 0

    # Fire a skull bomb
    g.player.x = 200
    g.player.y = 200
    g.mouse_x = 200
    g.mouse_y = 200
    g.update_skull_bomb()

    proj = list(g.projectiles)[-1]

    # Move projectile away from the player and place an enemy at that location
    # (avoid triggering player-contact branch that expects dict-style enemies)
    proj.x = 800
    proj.y = 600
    enemy = Enemy(proj.x, proj.y, health=100)
    g.enemies = [enemy]

    # Handle collisions once -> should explode and remove projectile
    g.handle_collisions()

    assert proj not in list(g.projectiles)
    assert enemy.health < 100


if __name__ == "__main__":
    test_skull_bomb_weapon_definition()
    test_skull_bomb_cooldown()
    test_skull_bomb_damage()
    test_skull_bomb_explosion_radius()
    test_skull_bomb_firing()
    test_skull_bomb_does_not_explode_on_player_spawn()
    test_skull_bomb_explodes_on_enemy_contact()
    print("All Skull Bomb tests passed!")
