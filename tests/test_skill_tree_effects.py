#!/usr/bin/env python3
"""Tests for elemental skill-tree effects on towers/statues (right column tiers).

Right-column tiers (4..6) grant per-slot bonuses: FIRE +10% damage per active slot, ICE +20% damage per active slot.
Fire-rate per-slot is +10% for FIRE/ICE but **+20%** for STORM (per design change).
"""

import os
import sys


from game import Game


def _expected_damage(base: int, slots: int) -> int:
    return int(round(base * (1.0 + 0.1 * slots)))


def _expected_damage_with_mult(base: int, slots: int, per_slot: float) -> int:
    """Generic expected damage helper where per_slot is the fractional increase."""
    return int(round(base * (1.0 + per_slot * slots)))


def _expected_fire_rate(base: int, slots: int) -> int:
    # Default helper for per-slot +10% fire-rate (used by FIRE and ICE)
    mult = 1.0 + 0.1 * slots
    return max(1, int(round(base / mult)))


def _expected_fire_rate_with_mult(base: int, slots: int, per_slot: float) -> int:
    # Generic helper where per_slot is the fractional increase (e.g. 0.2 for +20%)
    mult = 1.0 + per_slot * slots
    return max(1, int(round(base / mult)))


def test_fire_right_column_applies_to_fire_tower():
    g = Game()
    # ensure deterministic test state: clear fire right-column tiers
    for k in ("fire_4", "fire_5", "fire_6"):
        g.permanent_stats[k] = 0
    g.apply_permanent_stats()

    # ensure fire towers are active
    g.apply_tower("fire")

    base_dmg = getattr(g.left_tower, "_base_damage", g.left_tower.damage)
    # use the current fire_rate value as the baseline
    base_fr = g.left_tower.fire_rate

    # Activate one right-column slot (tier 4)
    g.permanent_stats["fire_4"] = 1
    g.apply_permanent_stats()

    assert g.left_tower.damage == _expected_damage(base_dmg, 1)
    assert abs(g.left_tower.fire_rate - base_fr) <= 1

    # also verify crit chance component for a fire tower projectile
    class DummyProj:
        def __init__(self):
            self.is_enemy_projectile = False
            self.damage = 10
            self.tower_type = "fire"
            self.source = "statue"

    class DummyEnemy:
        def __init__(self):
            self.burn_timer = 0

    proj = DummyProj()
    enemy = DummyEnemy()
    # right now only tier4 active -> +0.1 extra crit
    cs = g.collision_system
    import random

    random.random = lambda: 0.0
    dmg = cs._player_damage_vs_burning(proj, enemy, proj.damage)
    assert dmg == 15  # crit applied
    random.random = lambda: 0.99
    dmg = cs._player_damage_vs_burning(proj, enemy, proj.damage)
    assert dmg == 10

    # repeat for a storm tower projectile
    class DummyProj2(DummyProj):
        def __init__(self):
            super().__init__()
            self.tower_type = "storm"

    proj2 = DummyProj2()
    # activate storm right slot as well
    g.permanent_stats["storm_4"] = 1
    cs = g.collision_system
    random.random = lambda: 0.0
    dmg2 = cs._player_damage_vs_burning(proj2, enemy, proj2.damage)
    assert dmg2 == 15
    random.random = lambda: 0.99
    dmg2 = cs._player_damage_vs_burning(proj2, enemy, proj2.damage)
    assert dmg2 == 10

    # Activate two more (stacking)
    g.permanent_stats["fire_5"] = 1
    g.permanent_stats["fire_6"] = 1
    g.apply_permanent_stats()

    assert g.left_tower.damage == _expected_damage(base_dmg, 3)
    assert abs(g.left_tower.fire_rate - base_fr) <= 1


def test_storm_and_ice_right_column_apply_correctly():
    g = Game()

    # Storm
    for k in ("storm_4", "storm_5", "storm_6"):
        g.permanent_stats[k] = 0
    g.apply_permanent_stats()
    g.apply_tower("storm")
    base_dmg = getattr(g.left_tower, "_base_damage", g.left_tower.damage)
    base_fr = g.left_tower.fire_rate
    g.permanent_stats["storm_4"] = 1
    g.apply_permanent_stats()
    # damage no longer increases for storm right-column slots
    assert g.left_tower.damage == base_dmg
    # STORM still uses +20% fire-rate per slot
    assert (
        abs(g.left_tower.fire_rate - _expected_fire_rate_with_mult(base_fr, 1, 0.2))
        <= 1
    )

    # Ice
    for k in ("ice_4", "ice_5", "ice_6"):
        g.permanent_stats[k] = 0
    g.apply_permanent_stats()
    g.apply_tower("ice")
    base_dmg = getattr(g.left_tower, "_base_damage", g.left_tower.damage)
    base_fr = g.left_tower.fire_rate
    g.permanent_stats["ice_4"] = 1
    g.apply_permanent_stats()
    # ICE now grants +20% damage per right-column slot
    assert g.left_tower.damage == _expected_damage_with_mult(base_dmg, 1, 0.2)
    assert g.left_tower.fire_rate == _expected_fire_rate(base_fr, 1)


def test_storm_left_column_increases_chain_targets():
    """Each left-column STORM slot adds +1 chained target for storm statues."""
    g = Game()
    # ensure no left-column storm perks
    for k in ("storm_1", "storm_2", "storm_3"):
        g.permanent_stats[k] = 0
    g.apply_permanent_stats()

    # Apply storm towers and check baseline
    g.apply_tower("storm")
    base_chain = getattr(g.left_tower, "chain_targets", 3)
    assert base_chain == 3

    # Activate tier 1 -> +2 chain targets
    g.permanent_stats["storm_1"] = 1
    g.apply_permanent_stats()
    assert g.left_tower.chain_targets == base_chain + 2

    # Activate all three left slots -> +4 total (2 + 0 + 2); storm_2 is an on-kill explosion now
    g.permanent_stats["storm_2"] = 1
    g.permanent_stats["storm_3"] = 1
    g.apply_permanent_stats()
    assert g.left_tower.chain_targets == base_chain + 4
