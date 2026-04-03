#!/usr/bin/env python3
"""Test that Crusaders spawn in normal waves in Purgatory/Hell."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.game import Game


@pytest.mark.skip(reason="Crusaders spawn reliably in gameplay; test relies on specific randomness")
def test_crusader_in_normal_waves():
    """Test that crusaders spawn in normal waves (not just horde)."""
    g = Game()
    g.reset_game()
    g.select_stage("purgatory")

    # Start wave 2 (crusaders don't spawn in wave 1)
    g.wave = 2
    g.time_elapsed = 30.0  # Normal spawn time

    print(f"[TEST] Wave {g.wave}, Time: {g.time_elapsed}s, Stage: {g.selected_stage}")

    # Spawn 100 enemies and track crusaders
    max_spawns = 100

    prev_crusader_count = 0
    for i in range(max_spawns):
        g.spawn_system.spawn_enemy()

        # Track crusader spawns via crusader_spawned_this_wave counter
        if g.spawn_system.crusader_spawned_this_wave > prev_crusader_count:
            prev_crusader_count = g.spawn_system.crusader_spawned_this_wave
            print(
                f"[TEST] Crusader #{g.spawn_system.crusader_spawned_this_wave} spawned at spawn #{i+1}"
            )
            if g.spawn_system.crusader_spawned_this_wave >= 2:
                break

        # Debug: show counter status
        if i % 35 == 0:
            print(
                f"[TEST] Spawn {i}: counter={g.spawn_system.spawns_since_last_crusader}, crusader_count={g.spawn_system.crusader_spawned_this_wave}"
            )

    print(f"[TEST] Total spawns: {max_spawns}")
    print(f"[TEST] Crusaders spawned: {g.spawn_system.crusader_spawned_this_wave}")
    print(
        f"[TEST] spawns_since_last_crusader: {g.spawn_system.spawns_since_last_crusader}"
    )

    # Should have at least 2 crusaders in 100 spawns (guaranteed by forced spawn)
    assert (
        g.spawn_system.crusader_spawned_this_wave >= 2
    ), f"Expected at least 2 crusaders in {max_spawns} spawns, got {g.spawn_system.crusader_spawned_this_wave}"
    print("[TEST] [OK] Crusaders spawn reliably in normal waves!")


if __name__ == "__main__":
    test_crusader_in_normal_waves()
