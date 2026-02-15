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


def test_vigor_regenerates_health_every_5s_per_level():
    g = Game()
    # Apply permanent vigor and start a run
    g.permanent_stats["vigor"] = 2
    g.reset_game()

    max_hp = g.player.max_health
    # simulate player being wounded
    g.player.health = max_hp * 0.5

    # Advance exactly 5 seconds of game time (use update_game to force in-game updates)
    # Prevent incidental enemy contact during this deterministic timing test
    try:
        g.enemies = []
    except Exception:
        import pygame

        g.enemies = pygame.sprite.Group()
    import pygame

    g.enemy_projectiles = pygame.sprite.Group()

    # Prevent automatic spawns during this timing-sensitive test
    g.enemy_spawn_timer = 10**6
    try:
        g.enemy_manager.enemy_spawn_timer = 10**6
    except Exception:
        pass

    frames = 5 * g.fps
    for _ in range(frames):
        g.update_game()

    # Expected heal = 0.5 HP per level -> 1.0 HP total for level 2
    expected_heal = 0.5 * 2
    assert g.player.health == pytest.approx(
        min(max_hp, max_hp * 0.5 + expected_heal), rel=1e-6
    )


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


def test_structure_reduces_damage_and_grants_xp_bonus_on_kill():
    import pygame

    g = Game()
    # give one point of structure (3% dmg reduction + 3% XP)
    g.permanent_stats["structure"] = 1
    g.reset_game()

    # Player damage reduction multiplier should reflect -3% per level
    assert g.damage_reduction_multiplier == pytest.approx(1.0 - 0.03)
    assert g.player.damage_reduction_multiplier == pytest.approx(1.0 - 0.03)

    # Create a dummy enemy sprite that is already dead so update_game awards XP
    class DummyEnemy(pygame.sprite.Sprite):
        def __init__(self):
            super().__init__()
            self.health = 0
            self.max_health = 10
            self.enemy_type = "strong"  # base XP = 25
            # provide a rect so pygame.sprite functions don't crash; place off-player
            self.rect = pygame.Rect(0, 0, 8, 8)

        def kill(self):
            pass

    g.enemies = pygame.sprite.Group()
    e = DummyEnemy()
    g.enemies.add(e)

    # Run one update; enemy is dead and should award XP with multiplier
    g.update_game()

    # base XP for 'strong' = 25; with structure level 1 -> 25 * 1.03 = 25.75 -> rounded => 26
    assert g.player_xp == 26
