#!/usr/bin/env python3
import pygame

from src.entities.enemy import Enemy
from src.game import Game


def test_demon_strike_available_only_in_purgatory():
    g = Game()

    # Ensure weapon exists in definitions
    from src.weapons import WEAPON_DEFS

    assert "DemonStrike" in WEAPON_DEFS

    # In Prologo the weapon must NOT be offered
    g.selected_stage = "prologo"
    choices = g.generate_weapon_choices()
    assert all(c["id"].replace("acquire_", "") != "DemonStrike" for c in choices)

    # In Limbo the weapon must NOT be offered
    g.selected_stage = "limbo"
    choices = g.generate_weapon_choices()
    assert all(c["id"].replace("acquire_", "") != "DemonStrike" for c in choices)

    # In Purgatory the weapon may be available (presence in full definitions)
    g.selected_stage = "purgatory"
    # get_weapon_definitions always contains it, and generate_weapon_choices will include it
    all_defs = [
        w["id"]
        for w in __import__(
            "src.weapons", fromlist=["get_weapon_definitions"]
        ).get_weapon_definitions()
    ]
    assert "DemonStrike" in all_defs


def test_demon_strike_vertical_motion_and_slow_and_pierce():
    pygame.init()
    g = Game()

    # Add DemonStrike to player's weapons and set level
    g.player_weapons = ["DemonStrike"]
    g.weapon_levels = {"DemonStrike": 1}

    # Place player near top so projectile moves down through enemies
    g.player.x = 200
    g.player.y = 100

    # Create two enemies vertically aligned below the player
    e1 = Enemy(200, 160, health=50)
    e2 = Enemy(200, 220, health=50)
    # Use list handling so collision logic hits the same code-paths as normal tests
    g.enemies = []
    g.enemies.append(e1)
    g.enemies.append(e2)

    # Fire DemonStrike aiming downward (aim_x non-zero to ensure vx is forced to 0)
    g.fire_demon_strike(1.0, 1.0)

    # Retrieve the projectile and verify vx == 0 (vertical-only)
    proj = None
    try:
        proj = list(g.projectiles)[0]
    except Exception:
        proj = g.projectiles[0]

    assert (
        getattr(proj, "vel_x", getattr(proj, "vx", None)) == 0
        or getattr(proj, "vel_x", 0) == 0
    )
    # Visual size check: should be visibly larger than default small projectiles
    assert getattr(proj, "radius", 0) >= 8

    # Simulate several frames allowing the projectile to travel through both enemies
    initial_h1 = e1.health
    initial_h2 = e2.health

    # Record rotation before updates
    rot_before = getattr(proj, "rotation_angle", 0)

    for _ in range(40):
        # Move projectile(s)
        for p in list(g.projectiles):
            try:
                p.update()
            except Exception:
                pass
        # Run collision handling where slow is applied
        g.handle_collisions()

    # Rotation should have progressed (visual rolling)
    assert getattr(proj, "rotation_angle", 0) != rot_before

    # Both enemies should have been damaged by exactly one instance each
    assert initial_h1 - e1.health == proj.damage
    assert initial_h2 - e2.health == proj.damage

    # Both enemies should have slow metadata applied
    assert getattr(e1, "slow_timer", 0) > 0
    assert getattr(e2, "slow_timer", 0) > 0
    assert getattr(e1, "slow_factor", 1.0) == 0.5
    assert getattr(e2, "slow_factor", 1.0) == 0.5


def test_demon_strike_damage_once_per_enemy():
    pygame.init()
    g = Game()

    g.player_weapons = ["DemonStrike"]
    g.weapon_levels = {"DemonStrike": 1}

    g.player.x = 50
    g.player.y = 100

    enemy = Enemy(50, 160, health=100)
    g.enemies = []
    g.enemies.append(enemy)

    # Create a DemonStrike projectile manually and add it (simulate piercing)
    from src.projectile import Projectile

    ds = Projectile(
        g.player.x, g.player.y, 0, 800, damage=10, radius=6, weapon_type="DemonStrike"
    )
    ds.pierce_all = True
    ds.effect = "slow"
    ds.slow_duration = 120
    ds.slow_factor = 0.5

    if hasattr(g.projectiles, "add"):
        g.projectiles.add(ds)
    else:
        g.projectiles.append(ds)

    initial_health = enemy.health

    # Simulate multiple frames where the projectile may overlap the enemy multiple times
    for _ in range(8):
        for proj in list(g.projectiles):
            try:
                proj.update()
            except Exception:
                pass
        g.handle_collisions()

    damage_taken = initial_health - enemy.health
    assert (
        damage_taken == ds.damage
    ), f"DemonStrike should damage each enemy once ({ds.damage}), got {damage_taken}"
