#!/usr/bin/env python3
"""Unit tests for profile meta-progression persistence across sessions.

These tests verify that meta_level, meta_xp, and meta_points are correctly
saved to and loaded from profile JSON files, preventing regressions like the
March 14 2026 corruption issue where meta_level was reset to 1.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.game import Game
from src.game.persistence import (
    get_profile_info,
    load_permanent_stats,
    profile_path,
    save_permanent_stats,
)


@pytest.fixture
def temp_profile_dir(tmp_path):
    """Create a temporary directory for test profiles."""
    return tmp_path


def test_profile_save_includes_meta_level(tmp_path, monkeypatch):
    """Verify that save_permanent_stats writes meta_level to profile JSON."""
    # Redirect profile path to temp directory
    def mock_profile_path(slot):
        return tmp_path / f"profile_{slot}.json"

    monkeypatch.setattr("src.game.persistence.profile_path", mock_profile_path)
    monkeypatch.setattr("src.game.core.profile_path", mock_profile_path)

    g = Game()
    g.active_profile_slot = 1
    g.global_progress["meta_level"] = 5
    g.global_progress["meta_xp"] = 234
    g.global_progress["meta_points"] = 2

    save_permanent_stats(g)

    # Read the saved file directly
    profile_file = tmp_path / "profile_1.json"
    assert profile_file.exists()
    with open(profile_file) as f:
        data = json.load(f)

    # Verify meta values were saved
    assert data["global_progress"]["meta_level"] == 5
    assert data["global_progress"]["meta_xp"] == 234
    assert data["global_progress"]["meta_points"] == 2


def test_profile_load_restores_meta_level(tmp_path, monkeypatch):
    """Verify that load_permanent_stats correctly reads meta_level from JSON."""

    def mock_profile_path(slot):
        return tmp_path / f"profile_{slot}.json"

    monkeypatch.setattr("src.game.persistence.profile_path", mock_profile_path)
    monkeypatch.setattr("src.game.core.profile_path", mock_profile_path)

    # Create a profile file with specific meta values
    profile_file = tmp_path / "profile_2.json"
    profile_data = {
        "version": 1,
        "name": "TestProfile",
        "last_played": "2026-03-14T12:00:00",
        "permanent_stats": {"power": 1, "vigor": 2},
        "global_progress": {
            "meta_level": 17,
            "meta_xp": 18896,
            "meta_points": 5,
            "stages_cleared": {"limbo_final": True},
        },
    }
    with open(profile_file, "w") as f:
        json.dump(profile_data, f)

    # Load the profile
    g = Game()
    g.active_profile_slot = 2
    g.global_progress = {}  # Start fresh
    load_permanent_stats(g)

    # Verify all meta values were loaded
    assert g.global_progress["meta_level"] == 17
    assert g.global_progress["meta_xp"] == 18896
    assert g.global_progress["meta_points"] == 5
    assert g.global_progress["stages_cleared"]["limbo_final"] is True


def test_meta_level_survives_save_load_cycle(tmp_path, monkeypatch):
    """Regression test: meta_level should not reset to 1 after save/load."""

    def mock_profile_path(slot):
        return tmp_path / f"profile_{slot}.json"

    monkeypatch.setattr("src.game.persistence.profile_path", mock_profile_path)
    monkeypatch.setattr("src.game.core.profile_path", mock_profile_path)

    # Game 1: Save with high meta_level
    g1 = Game()
    g1.active_profile_slot = 1
    g1.global_progress["meta_level"] = 15
    g1.global_progress["meta_xp"] = 5000
    g1.global_progress["meta_points"] = 3
    save_permanent_stats(g1)

    # Game 2: Load the same profile
    g2 = Game()
    g2.active_profile_slot = 1
    g2.global_progress = {}
    load_permanent_stats(g2)

    # Verify meta_level was preserved (not reset to 1)
    assert g2.global_progress["meta_level"] == 15, (
        "meta_level was corrupted on load: "
        f"expected 15, got {g2.global_progress['meta_level']}"
    )
    assert g2.global_progress["meta_xp"] == 5000
    assert g2.global_progress["meta_points"] == 3


def test_multiple_profiles_independent_meta(tmp_path, monkeypatch):
    """Verify that different profile slots maintain independent meta values."""

    def mock_profile_path(slot):
        return tmp_path / f"profile_{slot}.json"

    monkeypatch.setattr("src.game.persistence.profile_path", mock_profile_path)
    monkeypatch.setattr("src.game.core.profile_path", mock_profile_path)

    # Profile 1: Level 10
    g1 = Game()
    g1.active_profile_slot = 1
    g1.global_progress["meta_level"] = 10
    g1.global_progress["meta_xp"] = 1000
    save_permanent_stats(g1)

    # Profile 2: Level 5
    g2 = Game()
    g2.active_profile_slot = 2
    g2.global_progress["meta_level"] = 5
    g2.global_progress["meta_xp"] = 500
    save_permanent_stats(g2)

    # Profile 3: Level 20
    g3 = Game()
    g3.active_profile_slot = 3
    g3.global_progress["meta_level"] = 20
    g3.global_progress["meta_xp"] = 5000
    save_permanent_stats(g3)

    # Reload each and verify independence
    g1_reload = Game()
    g1_reload.active_profile_slot = 1
    g1_reload.global_progress = {}
    load_permanent_stats(g1_reload)
    assert g1_reload.global_progress["meta_level"] == 10

    g2_reload = Game()
    g2_reload.active_profile_slot = 2
    g2_reload.global_progress = {}
    load_permanent_stats(g2_reload)
    assert g2_reload.global_progress["meta_level"] == 5

    g3_reload = Game()
    g3_reload.active_profile_slot = 3
    g3_reload.global_progress = {}
    load_permanent_stats(g3_reload)
    assert g3_reload.global_progress["meta_level"] == 20


def test_meta_xp_not_reset_to_zero(tmp_path, monkeypatch):
    """Verify that saved meta_xp is never reset to 0 on load."""

    def mock_profile_path(slot):
        return tmp_path / f"profile_{slot}.json"

    monkeypatch.setattr("src.game.persistence.profile_path", mock_profile_path)
    monkeypatch.setattr("src.game.core.profile_path", mock_profile_path)

    g = Game()
    g.active_profile_slot = 1
    # Set meta_xp to non-zero value (simulating accumulated XP)
    g.global_progress["meta_xp"] = 18896
    g.global_progress["meta_level"] = 17
    save_permanent_stats(g)

    # Load and verify XP wasn't reset
    g_reload = Game()
    g_reload.active_profile_slot = 1
    g_reload.global_progress = {}
    load_permanent_stats(g_reload)

    assert g_reload.global_progress["meta_xp"] == 18896, (
        "meta_xp was corrupted: "
        f"expected 18896, got {g_reload.global_progress['meta_xp']}"
    )


def test_profile_info_reflects_meta_level(tmp_path, monkeypatch):
    """Verify that get_profile_info returns correct meta_level without loading full game."""

    def mock_profile_path(slot):
        return tmp_path / f"profile_{slot}.json"

    monkeypatch.setattr("src.game.persistence.profile_path", mock_profile_path)

    # Create a test profile
    profile_file = tmp_path / "profile_1.json"
    profile_data = {
        "version": 1,
        "name": "HighLevel",
        "last_played": "2026-03-14T12:00:00",
        "permanent_stats": {},
        "global_progress": {
            "meta_level": 25,
            "meta_xp": 50000,
            "meta_points": 10,
            "stages_cleared": {},
        },
    }
    with open(profile_file, "w") as f:
        json.dump(profile_data, f)

    # Get profile info
    info = get_profile_info(1)

    # Verify meta_level is correctly retrieved
    assert info["meta_level"] == 25
    assert info["meta_xp"] == 50000
    assert info["meta_points"] == 10


def test_corrupted_profile_loads_with_defaults(tmp_path, monkeypatch):
    """If meta_level is missing from JSON, should default to 1 (not crash)."""

    def mock_profile_path(slot):
        return tmp_path / f"profile_{slot}.json"

    monkeypatch.setattr("src.game.persistence.profile_path", mock_profile_path)
    monkeypatch.setattr("src.game.core.profile_path", mock_profile_path)

    # Create a corrupted profile (missing meta_level)
    profile_file = tmp_path / "profile_1.json"
    profile_data = {
        "version": 1,
        "name": "Corrupted",
        "permanent_stats": {},
        "global_progress": {
            # meta_level is missing!
            "meta_xp": 100,
            "stages_cleared": {},
        },
    }
    with open(profile_file, "w") as f:
        json.dump(profile_data, f)

    # Load should not crash, should use defaults
    g = Game()
    g.active_profile_slot = 1
    g.global_progress = {"meta_level": 1}  # Pre-set default
    load_permanent_stats(g)

    # meta_xp loaded from file, but meta_level uses default (1)
    assert g.global_progress["meta_xp"] == 100
    assert g.global_progress["meta_level"] == 1  # Uses pre-existing default


def test_award_meta_xp_then_save(tmp_path, monkeypatch):
    """Integration: award XP, save profile, reload, verify persistence."""

    def mock_profile_path(slot):
        return tmp_path / f"profile_{slot}.json"

    monkeypatch.setattr("src.game.persistence.profile_path", mock_profile_path)
    monkeypatch.setattr("src.game.core.profile_path", mock_profile_path)

    g1 = Game()
    g1.active_profile_slot = 1
    g1.global_progress["meta_xp"] = 0
    g1.global_progress["meta_level"] = 1

    # Award XP (may trigger level-up)
    g1.award_meta_xp(600)
    meta_level_after = g1.global_progress["meta_level"]
    meta_xp_after = g1.global_progress["meta_xp"]

    # Save
    save_permanent_stats(g1)

    # Reload
    g2 = Game()
    g2.active_profile_slot = 1
    g2.global_progress = {}
    load_permanent_stats(g2)

    # Verify persistence
    assert g2.global_progress["meta_level"] == meta_level_after, (
        f"meta_level not persisted: "
        f"saved {meta_level_after}, loaded {g2.global_progress['meta_level']}"
    )
    assert g2.global_progress["meta_xp"] == meta_xp_after


def test_select_profile_preserves_meta(tmp_path, monkeypatch):
    """When selecting a profile, meta_level should load correctly."""

    def mock_profile_path(slot):
        return tmp_path / f"profile_{slot}.json"

    monkeypatch.setattr("src.game.persistence.profile_path", mock_profile_path)
    monkeypatch.setattr("src.game.core.profile_path", mock_profile_path)

    # Create profile 1 with baseline meta_level
    profile1_file = tmp_path / "profile_1.json"
    profile1_data = {
        "version": 1,
        "name": "Profile1",
        "permanent_stats": {},
        "global_progress": {
            "meta_level": 5,
            "meta_xp": 500,
            "meta_points": 1,
            "stages_cleared": {},
        },
    }
    with open(profile1_file, "w") as f:
        json.dump(profile1_data, f)

    # Create profile 2 with high meta_level
    profile2_file = tmp_path / "profile_2.json"
    profile2_data = {
        "version": 1,
        "name": "Profile2",
        "permanent_stats": {},
        "global_progress": {
            "meta_level": 12,
            "meta_xp": 3000,
            "meta_points": 4,
            "stages_cleared": {},
        },
    }
    with open(profile2_file, "w") as f:
        json.dump(profile2_data, f)

    # Game starts and auto-loads last profile (profile 2)
    g = Game()
    # If game loaded profile 2, verify it has correct meta_level
    if g.active_profile_slot == 2:
        assert g.global_progress["meta_level"] == 12
        assert g.global_progress["meta_xp"] == 3000
        assert g.global_progress["meta_points"] == 4
    # If game loaded profile 1, switch to profile 2
    else:
        g.select_profile(2)
        assert g.active_profile_slot == 2
        assert g.global_progress["meta_level"] == 12
        assert g.global_progress["meta_xp"] == 3000
        assert g.global_progress["meta_points"] == 4


def test_profile_meta_values_are_integers(tmp_path, monkeypatch):
    """Verify that meta_level, meta_xp, meta_points are always integers in saved files."""

    def mock_profile_path(slot):
        return tmp_path / f"profile_{slot}.json"

    monkeypatch.setattr("src.game.persistence.profile_path", mock_profile_path)
    monkeypatch.setattr("src.game.core.profile_path", mock_profile_path)

    g = Game()
    g.active_profile_slot = 1
    g.global_progress["meta_level"] = 7
    g.global_progress["meta_xp"] = 2500
    g.global_progress["meta_points"] = 3
    save_permanent_stats(g)

    # Read raw JSON
    profile_file = tmp_path / "profile_1.json"
    with open(profile_file) as f:
        data = json.load(f)

    # Verify types in JSON
    assert isinstance(data["global_progress"]["meta_level"], int)
    assert isinstance(data["global_progress"]["meta_xp"], int)
    assert isinstance(data["global_progress"]["meta_points"], int)
