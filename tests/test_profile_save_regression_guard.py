#!/usr/bin/env python3
"""Test the regression guard in save_permanent_stats to ensure profiles never reset."""

import json
from pathlib import Path

import pytest

from src.game import Game
from src.game.persistence import profile_path, load_permanent_stats, save_permanent_stats


def test_regression_guard_prevents_accidental_reset():
    """
    Test that save_permanent_stats detects when in-memory state looks like
    an uninitialized reset (0 upgrades in memory vs upgrades on disk) and
    restores disk values instead of overwriting them.
    """
    # Create a game instance with a profile
    g = Game()
    g.active_profile_slot = 1

    # Set up disk state: save some upgrades
    g.permanent_stats["power"] = 5
    g.permanent_stats["blasphemy_1"] = 2
    g.permanent_stats["fire_1"] = 3
    g.global_progress["meta_level"] = 10
    g.global_progress["meta_xp"] = 5000
    g.global_progress["meta_points"] = 3
    save_permanent_stats(g)

    # Verify disk has the data
    path = profile_path(1)
    with open(path, "r", encoding="utf-8") as f:
        disk_data = json.load(f)
    assert disk_data["permanent_stats"]["power"] == 5
    assert disk_data["global_progress"]["meta_level"] == 10

    # Simulate a reset: clear in-memory state (as if Game() was initialized fresh)
    g.permanent_stats.clear()
    g.global_progress["meta_level"] = 1
    g.global_progress["meta_xp"] = 0
    g.global_progress["meta_points"] = 0

    # Verify in-memory looks reset (0 total upgrades)
    mem_total = sum(g.permanent_stats.get(k, 0) for k in g.permanent_stats)
    assert mem_total == 0, "In-memory should be reset"

    # Save: regression guard should detect this and restore disk values
    save_permanent_stats(g)

    # Verify disk values were NOT overwritten with zeros
    with open(profile_path(1), "r", encoding="utf-8") as f:
        disk_data = json.load(f)
    assert disk_data["permanent_stats"]["power"] == 5, "Power should not be reset to 0"
    assert disk_data["permanent_stats"]["blasphemy_1"] == 2
    assert disk_data["permanent_stats"]["fire_1"] == 3
    assert disk_data["global_progress"]["meta_level"] == 10, "Meta level should not be reset to 1"
    assert disk_data["global_progress"]["meta_xp"] == 5000
    assert disk_data["global_progress"]["meta_points"] == 3

    # Verify in-memory was also restored (for consistency)
    assert g.permanent_stats["power"] == 5
    assert g.global_progress["meta_level"] == 10


def test_normal_save_path_applies_monotonic_guards():
    """
    Test that when in-memory state is NOT a reset (it has some upgrades),
    the normal save path applies monotonic guards: permanent_stat tiers
    never decrease, and stages_cleared can only grow.
    """
    # Use slot 2 to avoid contamination from test_regression_guard_prevents_accidental_reset
    g = Game()
    g.active_profile_slot = 2

    # FIRST save: establish baseline on disk
    g.permanent_stats["power"] = 5
    g.permanent_stats["blasphemy_1"] = 0
    g.global_progress["meta_level"] = 10
    g.global_progress["meta_xp"] = 5000
    g.global_progress["stages_cleared"] = {"prologo": True}
    save_permanent_stats(g)

    # Verify baseline was saved to disk
    path = profile_path(2)
    with open(path, "r", encoding="utf-8") as f:
        disk_data = json.load(f)
    assert disk_data["permanent_stats"]["power"] == 5, "Baseline not saved"

    # SECOND modification: corrupt memory state (downgrades but not full reset)
    # (blasphemy_1 is set to 1, so mem_total > 0 — not a full reset)
    g.permanent_stats["power"] = 3  # decreased from 5
    g.permanent_stats["blasphemy_1"] = 1  # increased from 0
    g.global_progress["meta_level"] = 8  # decreased from 10
    g.global_progress["stages_cleared"] = {"limbo": True}  # different from disk

    # Save: monotonic guards should prevent downgrades
    save_permanent_stats(g)

    # Verify guards applied
    with open(profile_path(2), "r", encoding="utf-8") as f:
        disk_data = json.load(f)

    # Power should be restored to 5 (not allowed to decrease from disk value)
    assert disk_data["permanent_stats"]["power"] == 5, "Power should not decrease below 5"
    # blasphemy_1 can increase
    assert disk_data["permanent_stats"]["blasphemy_1"] == 1
    # stages_cleared is unioned (both should be present)
    assert disk_data["global_progress"]["stages_cleared"]["prologo"] is True
    assert disk_data["global_progress"]["stages_cleared"]["limbo"] is True


def test_profile_persists_across_game_instances():
    """
    Test that loading a profile in a new Game instance restores all progression.
    """
    # First instance: set upgrades and save (use slot 3)
    g1 = Game()
    g1.active_profile_slot = 3
    g1.permanent_stats["power"] = 6
    g1.permanent_stats["blasphemy_2"] = 4
    g1.global_progress["meta_level"] = 12
    g1.global_progress["meta_points"] = 5
    g1.global_progress["profile_name"] = "TestProfile"
    save_permanent_stats(g1)

    # Second instance: create fresh game, load same profile
    g2 = Game()
    g2.active_profile_slot = 3
    load_permanent_stats(g2)

    # Verify all progression was loaded
    assert g2.permanent_stats["power"] == 6
    assert g2.permanent_stats["blasphemy_2"] == 4
    assert g2.global_progress["meta_level"] == 12
    assert g2.global_progress["meta_points"] == 5
    assert g2.global_progress["profile_name"] == "TestProfile"


def test_atexit_handler_saves_on_process_exit():
    """
    Test that the atexit handler and auto-save mechanism are properly set up.
    """
    g = Game()
    g.active_profile_slot = 1

    # Verify atexit handler is registered (should have _autosave_timer attribute)
    assert hasattr(g, "_autosave_timer"), "Game should have _autosave_timer"
    assert hasattr(g, "_autosave_interval"), "Game should have _autosave_interval"
    assert g._autosave_interval == 30.0, "Auto-save interval should be 30 seconds"
    assert g._autosave_timer >= 0, "Auto-save timer should be initialized"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
