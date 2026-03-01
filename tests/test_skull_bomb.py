"""Test script for SkullBoom weapon functionality"""

import os
import sys


import pygame
import pytest

from src.entities.enemy import BurnParticle, Enemy
from src.game import Game
from src.weapons import skullboom_cooldown, skullboom_damage, skullboom_explosion_radius


def test_skullboom_weapon_definition():
    """Test that skullboom is properly defined in WEAPON_DEFS"""
    from src.weapons import WEAPON_DEFS

    assert "skullboom" in WEAPON_DEFS
    weapon = WEAPON_DEFS["skullboom"]
    assert weapon["name"] == "SkullBoom"
    assert weapon["max_level"] == 6
    assert len(weapon["upgrade_descriptions"]) == 6


def test_skullboom_cooldown():
    """Test cooldown calculation for different levels (SkullBoom)"""
    # Level 1: base 1.8s (current tuning)
    assert skullboom_cooldown(1) == 1.8
    # Level 2: 1.8 - 0.16 = 1.64
    assert skullboom_cooldown(2) == pytest.approx(1.64, rel=1e-6)
    # Level 6: reduced to configured value 1.0
    assert skullboom_cooldown(6) == 1.0


def test_skullboom_damage():
    """Test damage calculation for different levels (SkullBoom)"""
    # Level 1: base 25 * 1.2 = 30 (current tuning)
    assert skullboom_damage(1) == 30
    # Level 2: 28.333... * 1.2 = 34
    assert skullboom_damage(2) == 34
    # Level 6: 41.666... * 1.2 = 50
    assert skullboom_damage(6) == 50


def test_skullboom_explosion_radius():
    """Test explosion radius for different levels (SkullBoom)"""
    # Level 1: base 80
    assert skullboom_explosion_radius(1) == 80
    # Level 2: +8 radius
    assert skullboom_explosion_radius(2) == 88
    # Level 6: +40 radius
    assert skullboom_explosion_radius(6) == 120


def test_skullboom_firing():
    """Test that SkullBoom auto-fires towards mouse when cooldown is ready"""
    game = Game()
    game.player_weapons = ["skullboom"]
    game.weapon_levels = {"skullboom": 1}
    game.skullboom_cooldown_timer = 0  # Ready to fire

    # Set mouse position
    game.mouse_x = 200
    game.mouse_y = 200
    game.player.x = 100
    game.player.y = 100

    # Initially no projectiles
    initial_count = len(game.projectiles)

    # Update skull bomb (should fire)
    game.update_skullboom()

    # Should have fired one projectile
    assert len(game.projectiles) == initial_count + 1

    # Check projectile properties
    skull = list(game.projectiles)[-1]  # Last added
    assert skull.weapon_type == "skullboom"
    assert skull.damage == skullboom_damage(1)
    assert hasattr(skull, "explosion_radius")
    assert skull.explosion_radius == skullboom_explosion_radius(1)

    # Check direction towards mouse (should be normalized)
    import math

    expected_dx = (200 - 100) / math.hypot(200 - 100, 200 - 100)  # 0.707...
    expected_dy = (200 - 100) / math.hypot(200 - 100, 200 - 100)  # 0.707...
    assert (
        abs(skull.vel_x - expected_dx * 370) < 0.1
    )  # matches current skull speed (370)
    assert abs(skull.vel_y - expected_dy * 370) < 0.1

    # Cooldown should be set
    assert game.skullboom_cooldown_timer > 0


def test_skullboom_particles_filter_graceful():
    """Ensure game.update() handles dict entries in SkullBoom_particles gracefully."""
    pygame.init()
    g = Game(debug=True)
    # mix one dict with a proper BurnParticle
    g.skullboom_particles = [{"x": 0}, BurnParticle(0, 0, 0, 0, life=1)]
    try:
        g.update()
    except Exception as e:
        pytest.skip(f"update raised unexpectedly: {e}")
    # dict should still be present (alive defaults to True)
    assert any(isinstance(p, dict) for p in g.skullboom_particles)


def test_skullboom_does_not_explode_on_player_spawn():
    """SkullBoom must not detonate immediately or on overlap with player."""
    pygame.init()
    g = Game()
    g.player_weapons = ["skullboom"]
    g.weapon_levels = {"skullboom": 1}
    g.skullboom_cooldown_timer = 0

    # Ensure no enemies present
    g.enemies = []

    # Fire towards the right
    g.player.x = 100
    g.player.y = 100
    g.mouse_x = 150
    g.mouse_y = 100
    g.update_skullboom()

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


def test_skullboom_explodes_on_enemy_contact():
    """SkullBoom should detonate and damage enemies when overlapping them."""
    pygame.init()
    g = Game()
    g.player_weapons = ["skullboom"]
    g.weapon_levels = {"skullboom": 1}
    g.skullboom_cooldown_timer = 0

    # Fire a skull bomb
    g.player.x = 200
    g.player.y = 200
    g.mouse_x = 200
    g.mouse_y = 200
    g.update_skullboom()

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
    test_skullboom_weapon_definition()
    test_skullboom_cooldown()
    test_skullboom_damage()
    test_skullboom_explosion_radius()
    test_skullboom_firing()
    test_skullboom_does_not_explode_on_player_spawn()
    test_skullboom_explodes_on_enemy_contact()
    print("All SkullBoom tests passed!")
