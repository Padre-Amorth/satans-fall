#!/usr/bin/env python3
"""Test crusader spawn in Purgatory horde."""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.game import Game
from src.game_constants import PURGATORY_HORDE_TIME_1

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)


def test_crusader_in_horde():
    """Test that crusaders spawn during Purgatory horde phase 5a (38s)."""
    g = Game()
    g.reset_game()
    g.select_stage("purgatory")

    print("[TEST] Starting at 30s before horde...")
    g.time_elapsed = PURGATORY_HORDE_TIME_1 - 30.0

    # Manually advance time to trigger horde
    print(f"[TEST] Advancing to {PURGATORY_HORDE_TIME_1 + 0.1}s...")
    g.time_elapsed = PURGATORY_HORDE_TIME_1 + 0.1
    g.spawn_system.update_enemy_spawning()

    assert getattr(g, "purgatory_horde_active", False), "Horde should be active"
    print("[TEST] [OK] Horde activated")

    # Advance to phase 5a (38 seconds into horde = spawns with crusaders)
    print(f"[TEST] Advancing to phase 5a (38s into horde, frame {38 * g.fps})...")
    g.purgatory_horde_elapsed = int(38 * g.fps)

    # Advance through ALL phases and count crusaders
    print(f"[TEST] Total phases: {len(g.purgatory_horde_schedule)}")

    crusader_count = 0
    for phase_idx, phase in enumerate(g.purgatory_horde_schedule):
        phase_time = phase.get("time", 0) / g.fps if g.fps else 0
        custom = phase.get("custom", {})
        crusader_in_phase = custom.get("crusader", 0)
        if crusader_in_phase > 0:
            print(
                f"[TEST] Phase {phase_idx} @ {phase_time:.0f}s: {crusader_in_phase} crusaders"
            )
            g.spawn_system._spawn_horde_batch(phase)
            crusader_count += crusader_in_phase

    # Check enemies
    enemies_list = (
        list(g.enemies.sprites()) if hasattr(g.enemies, "sprites") else g.enemies
    )
    crusaders = [e for e in enemies_list if getattr(e, "enemy_type", "") == "crusader"]

    print(f"[TEST] Total enemies: {len(enemies_list)}")
    print(f"[TEST] Crusaders found: {len(crusaders)}")
    for i, crusader in enumerate(crusaders):
        print(
            f"  Crusader {i+1}: x={crusader.x:.0f}, y={crusader.y:.0f}, health={crusader.health:.0f}"
        )

    assert (
        len(crusaders) > 0
    ), f"Expected crusaders in phase 5a, got none. Enemies: {[getattr(e, 'enemy_type', 'unknown') for e in enemies_list]}"
    print("[TEST] [OK] Crusaders spawned successfully in phase 5a!")


if __name__ == "__main__":
    test_crusader_in_horde()
