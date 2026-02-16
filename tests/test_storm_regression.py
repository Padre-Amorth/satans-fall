#!/usr/bin/env python3
import pygame

from src.entities.enemy import Enemy
from src.game import Game
from src.projectile import Projectile


def test_storm_chain_effect_once_object():
    pygame.init()
    g = Game()

    e1 = Enemy(400, 100, enemy_type="normal", health=20)
    e2 = Enemy(420, 100, enemy_type="normal", health=20)
    e3 = Enemy(440, 100, enemy_type="normal", health=20)

    try:
        g.enemies.empty()
        g.enemies.add(e1)
        g.enemies.add(e2)
        g.enemies.add(e3)
    except Exception:
        g.enemies = [e1, e2, e3]

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

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles = [proj]

    g.handle_collisions()

    # Visual effect should be appended once and projectile marked as chain applied
    assert len(getattr(g.game_state, "chain_lightning_effects", [])) == 1
    assert getattr(proj, "_chain_applied", False) is True


def test_storm_chain_effect_once_dict():
    pygame.init()
    g = Game()

    g.enemies = [
        {"x": 400, "y": 100, "health": 20, "max_health": 20},
        {"x": 420, "y": 100, "health": 20, "max_health": 20},
        {"x": 440, "y": 100, "health": 20, "max_health": 20},
    ]
    proj = {
        "x": 400,
        "y": 100,
        "vel_x": 0.0,
        "vel_y": 0.0,
        "damage": 5,
        "radius": 6,
        "source": "statue",
        "appearance": "storm_statue",
        "chain_targets": 3,
    }
    g.projectiles = [proj]

    g.handle_collisions()

    # chain effect appended once
    assert len(getattr(g.game_state, "chain_lightning_effects", [])) == 1
    assert proj.get("_chain_applied", False) is True
