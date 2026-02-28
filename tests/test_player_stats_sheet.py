#!/usr/bin/env python3
"""Tests for the player stats sheet renderer."""

import os
import sys

import pygame


def setup_dummy_sdl():
    # some rendering tests rely on a dummy video driver
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from game import Game  # noqa: E402


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


def test_player_stats_shows_satan_label_and_xp_bar(tmp_path):
    """The stats sheet should display the renamed meta progress section.

    Verify that the "Satan Level" header and accompanying XP bar are painted
    (i.e. not left as background pixels).  The exact coordinates aren't
    critical; a small sample region around the expected area is sufficient.
    """
    setup_dummy_sdl()
    g = Game()
    g.showing_player_stats = True
    g.draw_player_stats()

    surface = g.screen
    bg = surface.get_at((0, 0))[:3]  # type: ignore[index]

    left_x = g.width // 2 - 430
    found = False
    for dy in range(88, 120):
        for dx in range(0, 300, 10):
            px = left_x + dx
            if tuple(surface.get_at((px, dy))[:3]) != bg:
                found = True
                break
        if found:
            break
    assert found, "Satan Level label or XP bar not rendered (still background)"


def test_enemy_kill_counter_and_displays(tmp_path):
    from src.entities.enemy import Enemy

    g = Game()
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
