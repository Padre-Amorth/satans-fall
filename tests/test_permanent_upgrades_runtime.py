#!/usr/bin/env python3
"""Tests that upgrading/downgrading permanent stats via the UI updates in-game multipliers."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from game import Game


def test_clicking_power_updates_damage_multiplier():
    g = Game()
    # ensure we are in-game and showing the permanent upgrades menu
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    left_x = g.width // 2 - 420
    # power stat is at y = 140 (as defined in the config)
    pos = (left_x + 5, 140 + 5)

    # Ensure starting from a known baseline
    g.permanent_stats["power"] = 0
    before = g.permanent_stats.get("power", 0)
    g.handle_mouse_click(pos, button=1)  # left click to upgrade
    after = g.permanent_stats.get("power", 0)
    assert after == before + 1
    # multiplier should reflect the upgrade (+3% per level)
    assert g.damage_multiplier == pytest.approx(1.0 + after * 0.03)
    assert g.player.damage_multiplier == pytest.approx(g.damage_multiplier)


def test_vigor_regenerates_health_every_3s_per_level():
    g = Game()
    # Apply permanent vigor and start a run
    g.permanent_stats["vigor"] = 2
    g.reset_game()

    max_hp = g.player.max_health
    # simulate player being wounded
    g.player.health = max_hp * 0.5

    # Advance exactly 3 seconds of game time (use update_game to force in-game updates)
    frames = 3 * g.fps
    for _ in range(frames):
        g.update_game()

    # Expected heal = 1% max HP per level -> 2% of max HP
    expected_heal = max_hp * 0.01 * 2
    assert g.player.health == pytest.approx(min(max_hp, max_hp * 0.5 + expected_heal), rel=1e-6)


def test_clicking_adrenaline_updates_fire_rate_multiplier():
    g = Game()
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    left_x = g.width // 2 - 420
    pos = (left_x + 5, 230 + 5)  # adrenaline y = 230

    # set a known value then downgrade
    g.permanent_stats["adrenaline"] = 2
    g.save_permanent_stats()
    g.apply_permanent_stats()
    before = g.permanent_stats["adrenaline"]

    # right click to downgrade
    g.handle_mouse_click(pos, button=3)
    after = g.permanent_stats["adrenaline"]
    assert after == before - 1
    assert g.fire_rate_multiplier == pytest.approx(1.0 + after * 0.05)
    assert g.player.fire_rate_multiplier == pytest.approx(g.fire_rate_multiplier)
