#!/usr/bin/env python3
import pygame

from src.entities.enemy import Enemy
from src.game import Game
from src.projectile import Projectile


def test_storm_projectile_chains_object_enemies():
    pygame.init()
    g = Game()

    # Create three Enemy instances close together
    e1 = Enemy(400, 100, enemy_type="normal", health=20)
    e2 = Enemy(420, 100, enemy_type="normal", health=20)
    e3 = Enemy(440, 100, enemy_type="normal", health=20)

    # Place enemies in pygame Group
    try:
        g.enemies.empty()
        g.enemies.add(e1)
        g.enemies.add(e2)
        g.enemies.add(e3)
    except Exception:
        g.enemies = [e1, e2, e3]

    # Create a storm projectile object positioned on top of first enemy
    proj = Projectile(
        400,
        100,
        0.0,
        0.0,
        damage=5,
        radius=6,
        weapon_type=None,
        appearance="storm_statue",
    )
    proj.source = "statue"
    proj.chain_targets = 3

    # Add to projectiles
    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles = [proj]

    # Run collisions
    g.handle_collisions()

    # e1 should have taken 5 damage
    assert e1.health == e1.max_health - 5
    # chain targets should have been hit for double damage
    assert e2.health == e2.max_health - 10
    assert e3.health == e3.max_health - 10
