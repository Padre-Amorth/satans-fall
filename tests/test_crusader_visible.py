#!/usr/bin/env python3
"""Test that crusaders are visible/in enemies list."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.game import Game


def test_crusader_visible():
    """Test that crusaders actually appear in enemies list."""
    g = Game()
    g.reset_game()
    g.select_stage("purgatory")

    g.wave = 2
    g.time_elapsed = 30.0

    print(f"[TEST] Initial enemies: {len(g.enemies)}")

    # Spawn 100 enemies
    for i in range(100):
        g.spawn_system.spawn_enemy()

    # Check enemies
    if hasattr(g.enemies, "sprites"):
        enemies_list = list(g.enemies.sprites())
    else:
        enemies_list = list(g.enemies)

    crusaders = [e for e in enemies_list if getattr(e, "enemy_type", "") == "crusader"]
    all_types = {}
    for e in enemies_list:
        etype = getattr(e, "enemy_type", "unknown")
        all_types[etype] = all_types.get(etype, 0) + 1

    print(f"[TEST] Total enemies in list: {len(enemies_list)}")
    print(f"[TEST] Crusaders in enemy list: {len(crusaders)}")
    print(f"[TEST] Enemy type breakdown: {all_types}")
    print(
        f"[TEST] crusader_spawned_this_wave counter: {g.spawn_system.crusader_spawned_this_wave}"
    )

    if len(crusaders) > 0:
        for i, c in enumerate(crusaders):
            print(
                f"  Crusader {i+1}: type={getattr(c, 'enemy_type', '?')}, health={c.health:.0f}"
            )

    # Should have crusaders in both counter AND visible list
    assert (
        g.spawn_system.crusader_spawned_this_wave >= 2
    ), f"Counter says {g.spawn_system.crusader_spawned_this_wave}, expected >= 2"
    assert (
        len(crusaders) >= 2
    ), f"Visible crusaders in list: {len(crusaders)}, expected >= 2"
    print("[TEST] [OK] Crusaders are visible!")


if __name__ == "__main__":
    test_crusader_visible()
