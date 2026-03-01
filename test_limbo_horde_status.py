#!/usr/bin/env python3
"""Simple status monitor for limbo horde during gameplay."""

import os
import sys

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from src.game import Game


def test_horde_status():
    """Monitor horde status every frame."""
    g = Game(debug=True)
    g.fps = 60
    g.selected_stage = "limbo"

    print("[TEST] Starting horde status monitor")

    # Set stage to limbo_2 to trigger the actual horde event naturally
    g.selected_stage = "limbo_2"

    # Actually, for testing, let's manually trigger the horde but without the schedule
    g.limbo_horde_started = True
    g.limbo_horde_active = True
    g.limbo_horde_completed = False
    g.limbo_horde_boss_killed = False
    g.limbo_horde_ready_for_victory = False
    g.limbo_horde_schedule = []
    g.limbo_horde_phase_index = 0
    g.stage_start_countdown = 0
    g.stage_start_timer = 0

    # Manually spawn boss at a reasonable position
    g.spawn_system.spawn_boss("limbo_horde")
    print(f"[TEST] Boss spawned")

    if not g.bosses:
        print("[TEST] FAILURE: No boss!")
        return False

    boss = list(g.bosses)[0]
    print(f"[TEST] Boss type: {boss.enemy_type}, initial health: {boss.health}")
    print(f"[TEST] Player weapons: {list(g.active_weapons.keys()) if hasattr(g, 'active_weapons') else 'N/A'}")
    print(f"[TEST] Player weapons count: {len(g.active_weapons) if hasattr(g, 'active_weapons') else 'N/A'}")

    # Monitor status for 200 frames (about 3 seconds at 60fps)
    print("\n[TEST] Frame | Boss Health | Enemies | Bosses | Projectiles | Horde Status | Victory Timer | Victory Screen")
    print("[TEST] ------+-------------+---------+--------+-------------+--------------+---------------+---------------")

    for frame in range(200):
        g.update_game()

        boss_health = boss.health if boss in g.bosses else "DEAD"
        horde_status = f"active={getattr(g, 'limbo_horde_active', False)} completed={getattr(g, 'limbo_horde_completed', False)}"
        victory_timer = getattr(g, "limbo_horde_victory_timer", 0)
        showing_victory = getattr(g, "showing_victory", False)
        proj_count = len(g.projectiles)

        if frame % 20 == 0 or (boss not in g.bosses) or proj_count > 0:
            print(f"[TEST] {frame:5d} | {str(boss_health):11} | {len(g.enemies):7d} | {len(g.bosses):6d} | {proj_count:11d} | {horde_status} | {victory_timer:13d} | {showing_victory}")

        if showing_victory:
            print(f"[TEST] VICTORY SCREEN SHOWN at frame {frame}!")
            return True

        if boss not in g.bosses and not getattr(g, "limbo_horde_active", False):
            print(f"[TEST] Boss removed and horde inactive at frame {frame}")
            if getattr(g, "limbo_horde_completed", False):
                print(f"[TEST] Horde marked as completed")
            if getattr(g, "limbo_horde_victory_timer", 0) > 0:
                print(f"[TEST] Victory timer is {getattr(g, 'limbo_horde_victory_timer', 0)}")

    print(f"\n[TEST] FAILURE: Victory screen never appeared after 200 frames")
    print(f"[TEST] Final state: horde_active={getattr(g, 'limbo_horde_active', False)}, completed={getattr(g, 'limbo_horde_completed', False)}")
    return False


if __name__ == "__main__":
    success = test_horde_status()
    sys.exit(0 if success else 1)
