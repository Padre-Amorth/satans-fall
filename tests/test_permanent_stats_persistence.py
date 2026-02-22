#!/usr/bin/env python3
"""Test that permanent stats persist to disk when saved and are loaded on
new Game construction (using an override file path)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from game import Game


def test_permanent_stats_save_and_load(tmp_path):
    f = tmp_path / "perm_stats.json"

    # Create game and override file
    g1 = Game(permanent_stats_file=f)
    g1.permanent_stats["power"] = 4
    g1.permanent_stats["vigor"] = 2
    # Also set some arbitrary global progress
    g1.global_progress["bosses_defeated"] = 3
    g1.global_progress["tutorial_seen"] = True
    # meta keys should round-trip
    g1.global_progress["meta_xp"] = 5
    g1.global_progress["meta_level"] = 2
    g1.global_progress["meta_points"] = 1
    g1.global_progress.setdefault("stages_cleared", {})["prologo"] = True
    g1.save_permanent_stats()

    # New game should load the saved values
    g2 = Game(permanent_stats_file=f)
    assert g2.permanent_stats["power"] == 4
    assert g2.permanent_stats["vigor"] == 2
    assert g2.global_progress.get("bosses_defeated") == 3
    assert g2.global_progress.get("tutorial_seen") is True
    assert g2.global_progress.get("meta_xp") == 5
    assert g2.global_progress.get("meta_level") == 2
    assert g2.global_progress.get("meta_points") == 1
    assert g2.global_progress.get("stages_cleared", {}).get("prologo") is True

    # Clean up (tmp_path handled by pytest)


def test_load_prunes_legacy_keys(tmp_path):
    f = tmp_path / "perm_stats_legacy.json"
    # Simulate an older file that contains legacy 'tower' and 'statue' keys
    payload = {
        "permanent_stats": {
            "power": 2,
            "tower_fire_power": 5,
            "statue_count": 3,
        },
        "global_progress": {},
    }
    with open(f, "w", encoding="utf-8") as fh:
        import json

        json.dump(payload, fh)

    g = Game(permanent_stats_file=f)
    # legacy keys should have been pruned
    assert "tower_fire_power" not in g.permanent_stats
    assert "statue_count" not in g.permanent_stats
    # valid key should still exist
    assert g.permanent_stats.get("power") == 2
