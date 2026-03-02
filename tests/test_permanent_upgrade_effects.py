#!/usr/bin/env python3
"""Tests for permanent upgrade effects on player multipliers."""

import pytest

from src.game import Game


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
    # fire-rate multiplier still tracked separately
    assert pytest.approx(g.player.fire_rate_multiplier, rel=1e-6) == 1.0 + 4 * 0.05


def test_adrenaline_crit_description_includes_chance():
    g = Game()
    assert (
        g.permanent_stat_effect_text("adrenaline", 2)
        == "+5% fire rate/level (10% total); +2% crit chance/level (4% total)"
    )


def test_permanent_stat_effect_texts():
    g = Game()
    assert g.permanent_stat_effect_text("power", 5) == "+5% dmg/level (25% total)"
    assert (
        g.permanent_stat_effect_text("vigor", 3)
        == "+10 HP/level (30 HP total)\nHeal 0.5 HP every 5s/level (0.5 HP/5s)"
    )
    assert (
        g.permanent_stat_effect_text("adrenaline", 2)
        == "+5% fire rate/level (10% total); +2% crit chance/level (4% total)"
    )
    assert (
        g.permanent_stat_effect_text("structure", 4)
        == "-2% dmg taken/level (8% total); +3% XP/level (+12% XP total)"
    )
    # Blasphemy 1 now gives HP per level instead of damage
    assert (
        g.permanent_stat_effect_text("blasphemy_1", 3) == "+15 HP/level (45 HP total)"
    )
    # Blasphemy 2 provides flat regeneration, blasphemy 3 reduces damage taken
    assert (
        g.permanent_stat_effect_text("blasphemy_2", 2)
        == "Heal 0.5 HP every 2s/level (1 HP every 2s)"
    )
    assert (
        g.permanent_stat_effect_text("blasphemy_3", 2)
        == "-10% dmg taken/level (20% total)"
    )
    assert g.permanent_stat_effect_text("blasphemy_4", 3) == "+10% XP/level (30% total)"
    # Blasphemy 5 is now a blink ability; show its description even at level 0
    assert (
        g.permanent_stat_effect_text("blasphemy_5", 0)
        == "Blink: teleport in moving direction (spacebar)"
    )
    assert (
        g.permanent_stat_effect_text("blasphemy_5", 1)
        == "Blink: teleport in moving direction (spacebar)"
    )
