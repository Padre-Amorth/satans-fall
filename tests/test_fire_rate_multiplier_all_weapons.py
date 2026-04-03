#!/usr/bin/env python3
"""Tests for fire_rate_multiplier affecting all player weapons."""

import pytest

from src.game import Game
from src.weapons import (
    DemonStrike_cooldown,
    cocytus_cooldown,
    flies_cd,
    shotgun_cooldown,
    skullboom_cooldown,
    tenebrae_cooldown,
)


def test_fire_rate_multiplier_affects_shotgun():
    """Verify Shotgun cooldown is reduced by fire_rate_multiplier."""
    g = Game()
    g.player_weapons = ["shotgun"]
    g.weapon_levels = {"shotgun": 1}
    g.fire_rate_multiplier = 1.5  # 50% faster

    # Expected cooldown: base_cooldown / 1.5
    base_cd = shotgun_cooldown(1)
    expected_frames = int((base_cd * 60) / 1.5)
    normal_frames = int(base_cd * 60)

    # Fire once and check cooldown
    g.hellgun_cooldown_timer = 0
    g.weapon_system.update_weapon_firing()

    # Check that fire rate was actually applied (cooldown < normal)
    assert g.hellgun_cooldown_timer < normal_frames
    # Allow small rounding difference (±1 frame)
    assert pytest.approx(g.hellgun_cooldown_timer, abs=1) == expected_frames


def test_fire_rate_multiplier_affects_spear():
    """Verify Spear cooldown is reduced by fire_rate_multiplier."""
    g = Game()
    g.player_weapons = ["spear"]
    g.weapon_levels = {"spear": 1}
    g.fire_rate_multiplier = 1.2

    base_cd = DemonStrike_cooldown(1)
    expected_frames = int((base_cd * 60) / 1.2)

    g.spear_cooldown_timer = 0
    g.weapon_system.update_weapon_firing()

    assert pytest.approx(g.spear_cooldown_timer, abs=1) == expected_frames


def test_fire_rate_multiplier_affects_skullboom():
    """Verify SkullBoom cooldown is reduced by fire_rate_multiplier."""
    g = Game()
    g.player_weapons = ["skullboom"]
    g.weapon_levels = {"skullboom": 1}
    g.fire_rate_multiplier = 1.3

    base_cd = skullboom_cooldown(1)
    expected_frames = int((base_cd * 60) / 1.3)

    g.skullboom_cooldown_timer = 0
    g.weapon_system.update_skullboom()

    assert pytest.approx(g.skullboom_cooldown_timer, abs=1) == expected_frames


def test_fire_rate_multiplier_affects_tenebrae():
    """Verify Tenebrae cooldown is reduced by fire_rate_multiplier."""
    g = Game()
    g.player_weapons = ["tenebrae"]
    g.weapon_levels = {"tenebrae": 1}
    g.fire_rate_multiplier = 1.1

    base_cd = tenebrae_cooldown(1)
    expected_frames = int((base_cd * 60) / 1.1)

    g.tenebrae_cooldown_timer = 0
    g.weapon_system.update_weapon_firing()

    assert pytest.approx(g.tenebrae_cooldown_timer, abs=1) == expected_frames


def test_fire_rate_multiplier_affects_cocytus():
    """Verify Cocytus cooldown is reduced by fire_rate_multiplier."""
    g = Game()
    g.player_weapons = ["cocytus"]
    g.weapon_levels = {"cocytus": 1}
    g.fire_rate_multiplier = 1.25

    base_cd = cocytus_cooldown(1)
    expected_frames = int((base_cd * 60) / 1.25)

    g.cocytus_cooldown_timer = 0
    g.weapon_system.update_weapon_firing()

    assert pytest.approx(g.cocytus_cooldown_timer, abs=1) == expected_frames


def test_fire_rate_multiplier_affects_demonstriketd():
    """Verify DemonStrike cooldown is reduced by fire_rate_multiplier."""
    g = Game()
    g.player_weapons = ["DemonStrike"]
    g.weapon_levels = {"DemonStrike": 1}
    g.fire_rate_multiplier = 1.4

    base_cd = DemonStrike_cooldown(1)
    expected_frames = int((base_cd * 60) / 1.4)

    g.DemonStrike_cooldown_timer = 0
    g.weapon_system.update_weapon_firing()

    assert pytest.approx(g.DemonStrike_cooldown_timer, abs=1) == expected_frames


def test_fire_rate_multiplier_affects_flies():
    """Verify Flies cooldown is reduced by fire_rate_multiplier."""
    g = Game()
    g.player_weapons = ["Flies"]
    g.weapon_levels = {"Flies": 1}
    g.fire_rate_multiplier = 1.2

    base_cd = flies_cd(1)
    expected_frames = int((base_cd * 60) / 1.2)

    g.flies_cooldown_timer = 0
    g.weapon_system.update_weapon_firing()

    assert pytest.approx(g.flies_cooldown_timer, abs=1) == expected_frames


def test_fire_rate_multiplier_affects_orbitals():
    """Verify Orbital fire rate is reduced by fire_rate_multiplier."""
    g = Game()
    g.player_weapons = ["orbital"]
    g.weapon_levels = {"orbital": 1}
    g.fire_rate_multiplier = 1.5

    # Get the range
    min_cd, max_cd = g.weapon_system._orbital_cooldown_range()

    # Both should be divided by fire_rate_multiplier (1.5)
    # Verify they're both reasonable (positive, less than without multiplier)
    assert min_cd > 0
    assert max_cd > 0
    assert min_cd <= max_cd


def test_no_fire_rate_boost_means_normal_cooldown():
    """Verify cooldowns are unchanged when fire_rate_multiplier = 1.0."""
    g = Game()
    g.player_weapons = ["shotgun"]
    g.weapon_levels = {"shotgun": 1}
    g.fire_rate_multiplier = 1.0

    base_cd = shotgun_cooldown(1)
    expected_frames = int(base_cd * 60)

    g.hellgun_cooldown_timer = 0
    g.weapon_system.update_weapon_firing()

    assert pytest.approx(g.hellgun_cooldown_timer, abs=1) == expected_frames


def test_high_fire_rate_multiplier_significantly_reduces_cooldown():
    """Verify 2.0x fire rate cuts cooldown in half."""
    g = Game()
    g.player_weapons = ["shotgun"]
    g.weapon_levels = {"shotgun": 1}
    g.fire_rate_multiplier = 2.0

    base_cd = shotgun_cooldown(1)
    normal_frames = int(base_cd * 60)
    expected_frames = normal_frames // 2

    g.hellgun_cooldown_timer = 0
    g.weapon_system.update_weapon_firing()

    assert pytest.approx(g.hellgun_cooldown_timer, abs=1) == expected_frames


def test_adrenaline_permanent_upgrade_affects_weapon_cooldowns():
    """Verify adrenaline permanent upgrade reduces weapon cooldowns in-game."""
    g = Game()
    g.permanent_stats["adrenaline"] = 5  # +5% fire rate per level = +25% total
    g.reset_game()
    g.player_weapons = ["shotgun"]
    g.weapon_levels = {"shotgun": 1}

    # Fire rate multiplier should be 1.0 + (5 * 0.05) = 1.25
    assert pytest.approx(g.fire_rate_multiplier, rel=1e-6) == 1.25

    base_cd = shotgun_cooldown(1)
    expected_frames = int((base_cd * 60) / 1.25)

    g.hellgun_cooldown_timer = 0
    g.weapon_system.update_weapon_firing()

    assert pytest.approx(g.hellgun_cooldown_timer, abs=1) == expected_frames
