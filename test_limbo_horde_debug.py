#!/usr/bin/env python3
"""Debug test for limbo horde victory."""

import os
import sys

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from src.game import Game


def test_horde_debug():
    """Test horde with full debug output."""
    g = Game(debug=True)
    g.fps = 60
    g.selected_stage = "limbo"

    print("[TEST] Starting limbo game")

    # Manually set horde state
    g.limbo_horde_started = True
    g.limbo_horde_active = True
    g.limbo_horde_completed = False
    g.limbo_horde_boss_killed = False
    g.limbo_horde_ready_for_victory = False

    print("[TEST] Horde state initialized")

    # Spawn boss
    g.spawn_system.spawn_boss("limbo_horde")
    print(f"[TEST] Boss spawned. Bosses count: {len(g.bosses)}")

    if g.bosses:
        boss = list(g.bosses)[0]
        print(f"[TEST] Boss type: {boss.enemy_type}, Health: {boss.health}")

        # Do a few updates while boss is alive
        print("[TEST] Doing 5 updates with boss alive...")
        for i in range(5):
            g.update()
            print(f"  Update {i}: enemies={len(g.enemies)}, bosses={len(g.bosses)}, "
                  f"ready_for_victory={getattr(g, 'limbo_horde_ready_for_victory', False)}, "
                  f"completed={getattr(g, 'limbo_horde_completed', False)}, "
                  f"timer={getattr(g, 'limbo_horde_victory_timer', 0)}")

        # Kill boss
        print("[TEST] Killing boss...")
        boss.health = 0

        # Do updates after boss death
        print("[TEST] Doing 10 updates after boss death...")
        for i in range(10):
            g.update()
            print(f"  Update {i}: enemies={len(g.enemies)}, bosses={len(g.bosses)}, "
                  f"ready_for_victory={getattr(g, 'limbo_horde_ready_for_victory', False)}, "
                  f"completed={getattr(g, 'limbo_horde_completed', False)}, "
                  f"timer={getattr(g, 'limbo_horde_victory_timer', 0)}")

        # Check final state
        timer = getattr(g, "limbo_horde_victory_timer", 0)
        print(f"\n[TEST] Final timer: {timer}")
        if timer > 0:
            print("[TEST] SUCCESS: Victory timer started!")
            return True
        else:
            print("[TEST] FAILURE: Victory timer not started")
            return False
    else:
        print("[TEST] FAILURE: Boss not spawned")
        return False


if __name__ == "__main__":
    success = test_horde_debug()
    sys.exit(0 if success else 1)
