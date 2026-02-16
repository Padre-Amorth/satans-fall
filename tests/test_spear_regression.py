#!/usr/bin/env python3
import pygame

from src.entities.enemy import Enemy
from src.game import Game
from src.projectile import Projectile


def test_spear_pierces_multiple_enemies_once_each():
    pygame.init()
    g = Game()

    # Use list for enemies to exercise non-sprite path
    g.enemies = []

    # Place player and multiple enemies aligned horizontally
    g.player.x = 50
    g.player.y = 100
    enemies = [Enemy(120 + i * 60, 100, health=100) for i in range(3)]
    for e in enemies:
        g.enemies.append(e)

    # Create spear projectile and add to projectiles (support Group/list)
    spear = Projectile(
        g.player.x, g.player.y, 800, 0, damage=12, radius=6, weapon_type="spear"
    )
    spear.pierce_all = True
    if hasattr(g.projectiles, "add"):
        g.projectiles.add(spear)
    else:
        g.projectiles.append(spear)

    # Simulate several frames so spear travels through all enemies
    for _ in range(30):
        for proj in list(g.projectiles):
            try:
                proj.update()
            except Exception:
                pass
        g.handle_collisions()

    # Each enemy should be damaged exactly once
    for e in enemies:
        assert (
            e.health == e.max_health - spear.damage
        ), f"Enemy at {e.x} was not hit exactly once"


def test_spear_handles_dict_enemies_once():
    pygame.init()
    g = Game()

    # Dict-style enemies (backwards compatibility path)
    g.enemies = []
    g.player.x = 50
    g.player.y = 100
    dict_enemies = [
        {"x": 120 + i * 60, "y": 100, "health": 100, "radius": 12} for i in range(2)
    ]
    for d in dict_enemies:
        g.enemies.append(d)

    spear = Projectile(
        g.player.x, g.player.y, 800, 0, damage=8, radius=6, weapon_type="spear"
    )
    spear.pierce_all = True
    if hasattr(g.projectiles, "add"):
        g.projectiles.add(spear)
    else:
        g.projectiles.append(spear)

    for _ in range(30):
        for proj in list(g.projectiles):
            try:
                proj.update()
            except Exception:
                pass
        g.handle_collisions()

    for d in dict_enemies:
        assert (
            d["health"] == 100 - spear.damage
        ), f"Dict enemy at {d['x']} was not hit exactly once"


def test_projectile_reset_clears_hit_ids():
    p = Projectile(0, 0, 0, 0)
    # Simulate hits
    p._hit_ids.add(123)
    assert 123 in p._hit_ids
    p.reset(0, 0, 0, 0)
    assert p._hit_ids == set(), "reset should clear _hit_ids"
