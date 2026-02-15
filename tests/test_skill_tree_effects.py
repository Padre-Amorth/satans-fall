#!/usr/bin/env python3
"""Tests for elemental skill-tree effects on towers/statues (right column tiers).

Right-column tiers (4..6) grant per-slot bonuses: FIRE +10% damage per active slot, ICE +20% damage per active slot.
Fire-rate per-slot is +10% for FIRE/ICE but **+20%** for STORM (per design change).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
    base_fr = getattr(g.left_tower, "_base_fire_rate", g.left_tower.fire_rate)

    # Activate one right-column slot (tier 4)
    g.permanent_stats["fire_4"] = 1
    g.apply_permanent_stats()

    assert g.left_tower.damage == _expected_damage(base_dmg, 1)
    assert g.left_tower.fire_rate == _expected_fire_rate(base_fr, 1)

    # Activate two more (stacking)
    g.permanent_stats["fire_5"] = 1
    g.permanent_stats["fire_6"] = 1
    g.apply_permanent_stats()

    assert g.left_tower.damage == _expected_damage(base_dmg, 3)
    assert g.left_tower.fire_rate == _expected_fire_rate(base_fr, 3)


def test_storm_and_ice_right_column_apply_correctly():
    g = Game()

    # Storm
    for k in ("storm_4", "storm_5", "storm_6"):
        g.permanent_stats[k] = 0
    g.apply_permanent_stats()
    g.apply_tower("storm")
    base_dmg = getattr(g.left_tower, "_base_damage", g.left_tower.damage)
    base_fr = getattr(g.left_tower, "_base_fire_rate", g.left_tower.fire_rate)
    g.permanent_stats["storm_4"] = 1
    g.apply_permanent_stats()
    assert g.left_tower.damage == _expected_damage(base_dmg, 1)
    # STORM uses +20% fire-rate per slot
    assert g.left_tower.fire_rate == _expected_fire_rate_with_mult(base_fr, 1, 0.2)

    # Ice
    for k in ("ice_4", "ice_5", "ice_6"):
        g.permanent_stats[k] = 0
    g.apply_permanent_stats()
    g.apply_tower("ice")
    base_dmg = getattr(g.left_tower, "_base_damage", g.left_tower.damage)
    base_fr = getattr(g.left_tower, "_base_fire_rate", g.left_tower.fire_rate)
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
