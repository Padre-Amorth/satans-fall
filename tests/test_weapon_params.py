#!/usr/bin/env python3
"""Tests for centralized weapon parameter helpers and integration."""

from src.game import Game
from src.weapons import (
    flies_damage_heal_mult,
    flies_projectile_count,
    orbital_cooldown_range,
    shotgun_cooldown,
    shotgun_pellets,
    spear_cooldown,
)


def test_shotgun_pellets_and_fire():
    game = Game()
    game.player_weapons = ["shotgun"]

    for level, expected_pellets in [(1, 4), (2, 5), (3, 5), (4, 6), (5, 6), (6, 7)]:
        game.weapon_levels = {"shotgun": level}
        # clean projectiles
        game.projectiles.empty()
        game.fire_hellgun(0, -500)
        projs = [p for p in game.projectiles]
        assert len(projs) == shotgun_pellets(
            level
        ), f"Expected {shotgun_pellets(level)} pellets at level {level}, got {len(projs)}"

        # Pellets should be 2px larger in radius compared to legacy base (base 5 -> now 7)
        if projs:
            expected_radius = int(5 * game.projectile_size_multiplier) + 2
            assert (
                projs[0].radius == expected_radius
            ), f"Pellet radius should be {expected_radius}, got {projs[0].radius}"

    # spread_deg was increased to slightly boost separation between pellets
    from src.weapons import WEAPON_DEFS

    assert (
        WEAPON_DEFS["shotgun"]["spread_deg"] == 15
    ), "Hellgun spread should be set to 15 degrees"


def test_shotgun_and_spear_cooldowns():
    assert abs(shotgun_cooldown(1) - 1.5) < 1e-6
    assert abs(shotgun_cooldown(2) - 1.35) < 1e-6
    assert shotgun_cooldown(10) >= 0.4

    assert abs(spear_cooldown(0) - 0.6) < 1e-6
    assert abs(spear_cooldown(3) - max(0.15, 0.6 - 3 * 0.06)) < 1e-6


def test_flies_projectiles_and_mult():
    # Base changed: lv1 now fires 2 projectiles
    assert flies_projectile_count(1) == 2
    assert flies_projectile_count(2) == 2  # still 2 until lvl3
    assert flies_projectile_count(3) == 3
    assert flies_projectile_count(4) == 3  # additional projectile at lvl5
    assert flies_projectile_count(5) == 4
    assert flies_projectile_count(6) == 4

    # Damage/heal multipliers bump at levels 2,4,6
    m1, h1 = flies_damage_heal_mult(1)
    m2, h2 = flies_damage_heal_mult(2)
    m3, h3 = flies_damage_heal_mult(3)
    m4, h4 = flies_damage_heal_mult(4)
    m5, h5 = flies_damage_heal_mult(5)
    m6, h6 = flies_damage_heal_mult(6)

    assert abs(m1 - 1.0) < 1e-6
    assert m2 > m1
    assert m3 == m2  # no increase at lvl3
    assert m4 > m3
    assert m5 == m4  # no increase at lvl5
    assert m6 > m5


def test_orbital_cooldown_range():
    min0, max0 = orbital_cooldown_range(0)
    min4, max4 = orbital_cooldown_range(4)
    assert min0 <= max0
    assert min4 <= max4
    assert min4 <= min0 or max4 <= max0 or (min4 != min0)

    # baseline 40–100 becomes ~53–133 after 4/3 slowdown; allow ±1 fuzz
    assert 52 <= min0 <= 54
    assert 132 <= max0 <= 134
