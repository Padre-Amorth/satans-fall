#!/usr/bin/env python3
import os
import sys

import pygame

# ensure project root on path when tests are run directly

from src.entities.enemy import Enemy
from src.game import Game


def test_spear_hits_enemy_only_once():
    pygame.init()
    g = Game()

    # Use a plain list for enemies to exercise the non-sprite code paths
    g.enemies = []

    # Place player and enemy aligned horizontally
    g.player.x = 50
    g.player.y = 100
    enemy = Enemy(120, 100, health=100)
    g.enemies.append(enemy)

    # Create a spear projectile manually and add it to the game's projectile container
    from src.projectile import Projectile

    spear = Projectile(
        g.player.x, g.player.y, 800, 0, damage=10, radius=6, weapon_type="spear"
    )
    spear.pierce_all = True
    if hasattr(g.projectiles, "add"):
        g.projectiles.add(spear)
    else:
        g.projectiles.append(spear)

    # Retrieve spear reference (support both Group and list)
    spear_ref = None
    try:
        spear_ref = list(g.projectiles)[0]
    except Exception:
        spear_ref = g.projectiles[0]
    spear = spear_ref

    initial_health = enemy.health

    # Simulate a few frames where the spear may overlap the enemy multiple times
    for _ in range(8):
        # Update projectile positions
        for proj in list(g.projectiles):
            try:
                proj.update()
            except Exception:
                pass
        # Run collision handling
        g.handle_collisions()

    damage_taken = initial_health - enemy.health
    assert (
        damage_taken == spear.damage
    ), f"Spear should damage once ({spear.damage}), got {damage_taken}"


def test_spear_fire_radius_adjusted():
    """Firing a spear should use the reduced base radius (7× multiplier)."""
    g = Game(debug=True)
    g.weapon_levels = {"spear": 1}
    g.player_weapons = ["spear"]
    g.fire_spear(1.0, 0.0)
    projs = list(g.projectiles)
    assert projs, "Expected spear projectile"
    p = projs[-1]
    expected = int(7 * g.projectile_size_multiplier * 1.1)
    assert p.radius == expected, f"radius {p.radius} != expected {expected}"
