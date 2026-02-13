#!/usr/bin/env python3
"""Tests for permanent upgrade effects on player multipliers."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from game import Game


def test_power_gives_three_percent_per_level():
    g = Game()
    g.permanent_stats["power"] = 5
    # Apply reset to ensure values are applied to the player
    g.reset_game()
    assert pytest.approx(g.player.damage_multiplier, rel=1e-6) == 1.0 + 5 * 0.03


def test_adrenaline_gives_five_percent_fire_rate_per_level():
    g = Game()
    g.permanent_stats["adrenaline"] = 4
    g.reset_game()
    assert pytest.approx(g.player.fire_rate_multiplier, rel=1e-6) == 1.0 + 4 * 0.05


def test_permanent_stat_effect_texts():
    g = Game()
    assert g.permanent_stat_effect_text("power", 5) == "+3% dmg/level (15% total)"
    assert g.permanent_stat_effect_text("vigor", 3) == "+10 HP/level (30 HP total); +1% max HP regen every 3s/level"
    assert g.permanent_stat_effect_text("adrenaline", 2) == "+5% fire rate/level (10% total)"
    assert g.permanent_stat_effect_text("structure", 4) == "-5% dmg taken/level (20% total)"
