"""Test script for Skull Bomb weapon functionality"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
    # Level 1: base 2.0s
    assert skull_bomb_cooldown(1) == 2.0
    # Level 2: reduced by 0.15
    assert skull_bomb_cooldown(2) == 1.85
    # Level 6: reduced by 5*0.15 = 0.75, so 2.0 - 0.75 = 1.25
    assert skull_bomb_cooldown(6) == 1.25


def test_skull_bomb_damage():
    """Test damage calculation for different levels"""
    # Level 1: base 20 + 20% = 24
    assert skull_bomb_damage(1) == 24
    # Level 2: 22 + 20% = 26.4 → 26
    assert skull_bomb_damage(2) == 26
    # Level 6: 30 + 20% = 36
    assert skull_bomb_damage(6) == 36


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
    assert abs(skull.vel_x - expected_dx * 320) < 0.1  # Close enough (20% slower)
    assert abs(skull.vel_y - expected_dy * 320) < 0.1

    # Cooldown should be set
    assert game.skull_bomb_cooldown_timer > 0


if __name__ == "__main__":
    test_skull_bomb_weapon_definition()
    test_skull_bomb_cooldown()
    test_skull_bomb_damage()
    test_skull_bomb_explosion_radius()
    test_skull_bomb_firing()
    print("All Skull Bomb tests passed!")
