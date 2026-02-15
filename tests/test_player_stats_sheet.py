#!/usr/bin/env python3
"""Tests for the player stats sheet renderer."""

import os
import sys

import pygame

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from game import Game


def test_draw_player_stats_does_not_crash():
    g = Game()
    # set some values
    g.player_level = 4
    g.player_xp = 120
    g.score = 5000
    g.damage_multiplier = 1.3
    g.fire_rate_multiplier = 0.85
    g.player_weapons = ["shotgun", "orbital"]
    g.weapon_levels = {"shotgun": 2, "orbital": 1}
    g.upgrade_levels = {"damage": 1, "max_health": 2}

    # Show the sheet and call the draw function
    g.showing_player_stats = True
    g.enemies_killed_this_run = 7
    g.draw_player_stats()  # should not raise

    # Also draw UI to ensure integration point works
    g.draw_ui()


def test_enemy_kill_counter_and_displays(tmp_path):
    from src.entities.enemy import Enemy

    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))
    # counter resets on new run
    g.reset_run()
    assert getattr(g, "enemies_killed_this_run", 0) == 0

    # Sprite enemy: kill should increment counter (Enemy.kill override + Game.record_enemy_kill)
    e = Enemy(100, 100, enemy_type="normal", health=1)
    try:
        g.enemies.add(e)
    except Exception:
        # handle list-based implementations in tests
        try:
            g.enemies.append(e)
        except Exception:
            pass
    # kill via method
    e.kill()
    assert g.enemies_killed_this_run == 1

    # Ensure player stats / game over drawing accept and show the value (no crash)
    g.enemies_killed_this_run = 42
    g.showing_player_stats = True
    g.draw_player_stats()
    g.game_over()
    g.draw_game_over()


def test_toggle_player_stats_with_tab():
    g = Game()
    # Start in-game so the Tab toggle is active
    g.showing_stage_menu = False
    assert not g.showing_player_stats
    g.handle_keydown(pygame.K_TAB)
    assert g.showing_player_stats
    assert g.paused is True
    g.handle_keydown(pygame.K_TAB)
    assert not g.showing_player_stats
    assert g.paused is False


def test_player_stats_excludes_tower_and_elemental_keys():
    g = Game()
    g.permanent_stats.update(
        {
            "tower_fire_power": 3,
            "fire_1": 1,
            "storm_1": 1,
            "ice_1": 1,
            "power": 2,
            "vigor": 1,
        }
    )
    items = g._player_stats_display_items()
    keys = [k for k, v in items]
    # tower/statue and elemental-prefixed keys should be excluded
    assert "tower_fire_power" not in keys
    assert "fire_1" not in keys
    assert "storm_1" not in keys
    assert "ice_1" not in keys
    # normal stats remain
    assert "power" in keys
    assert "vigor" in keys
