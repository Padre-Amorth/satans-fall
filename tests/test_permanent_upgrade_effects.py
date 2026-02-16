#!/usr/bin/env python3
"""Tests for permanent upgrade effects on player multipliers."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from game import Game


def test_power_gives_five_percent_per_level():
    g = Game()
    # Ensure other permanent stats don't interfere with the damage calculation
    g.permanent_stats["blasphemy_1"] = 0
    g.permanent_stats["power"] = 5
    # Apply reset to ensure values are applied to the player
    g.reset_game()
    assert pytest.approx(g.player.damage_multiplier, rel=1e-6) == 1.0 + 5 * 0.05


def test_adrenaline_gives_five_percent_fire_rate_per_level():
    g = Game()
    g.permanent_stats["adrenaline"] = 4
    g.reset_game()
    assert pytest.approx(g.player.fire_rate_multiplier, rel=1e-6) == 1.0 + 4 * 0.05


def test_permanent_stat_effect_texts():
    g = Game()
    assert g.permanent_stat_effect_text("power", 5) == "+5% dmg/level (25% total)"
    assert (
        g.permanent_stat_effect_text("vigor", 3)
        == "+10 HP/level (30 HP total); +0.5 HP every 5s/level (1.5 HP every 5s)"
    )
    assert (
        g.permanent_stat_effect_text("adrenaline", 2)
        == "+5% fire rate/level (10% total)"
    )
    assert (
        g.permanent_stat_effect_text("structure", 4)
        == "-3% dmg taken/level (12% total); +3% XP/level (+12% XP total)"
    )
    # Blasphemy 1 is +10% damage per level (3-level slot)
    assert (
        g.permanent_stat_effect_text("blasphemy_1", 3) == "+10% dmg/level (30% total)"
    )
    # New blasphemies: blasphemy_2 = +20 HP/level, blasphemy_3 = +10% FR/level, blasphemy_4 = +10% XP/level
    assert (
        g.permanent_stat_effect_text("blasphemy_2", 2) == "+20 HP/level (40 HP total)"
    )
    assert (
        g.permanent_stat_effect_text("blasphemy_3", 2)
        == "+10% fire rate/level (20% total)"
    )
    assert g.permanent_stat_effect_text("blasphemy_4", 3) == "+10% XP/level (30% total)"
