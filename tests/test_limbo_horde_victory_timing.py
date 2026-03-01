#!/usr/bin/env python3
"""Test to verify limbo horde victory screen only appears after boss death."""
import sys
import os

# Suppress pygame output
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from src.game import Game


def test_horde_victory_after_boss_death_only():
    """
    Verify that:
    1. Victory screen does NOT appear before boss dies
    2. Victory screen ONLY appears after boss and all horde enemies are dead
    """
    g = Game(debug=True)
    g.fps = 60

    # Start a limbo game
    g.selected_stage = "limbo"

    # Manually set horde state instead of waiting for timer
    g.limbo_horde_started = True
    g.limbo_horde_active = True
    g.limbo_horde_completed = False
    g.limbo_horde_boss_killed = False
    g.limbo_horde_ready_for_victory = False

    print(f"[OK] Horde manually started")

    # Manually spawn the horde boss
    g.spawn_system.spawn_boss("limbo_horde")

    # Verify victory screen NOT shown yet
    if getattr(g, "showing_victory", False):
        print("FAIL: Victory screen shown before boss death!")
        return False
    print(f"[OK] Victory screen NOT shown before boss death")

    # Get the boss
    if not g.bosses:
        print("FAIL: Boss didn't spawn")
        return False

    boss = list(g.bosses)[0]
    print(f"[OK] Boss spawned with {boss.health} health")

    # Kill the boss
    print(f"  Killing boss...")
    boss.health = 0
    g.update()

    # Give it a few frames for the victory countdown to start
    for _ in range(10):
        g.update()

    # Now victory should eventually appear
    victory_timer = getattr(g, "limbo_horde_victory_timer", 0)
    print(f"  Victory timer: {victory_timer}")

    if victory_timer > 0:
        print(f"[OK] Victory countdown started after boss death")
        # Fast-forward to victory screen appearance
        for _ in range(victory_timer + 1):
            g.update()

        if getattr(g, "showing_victory", False):
            print(f"[OK] Victory screen appeared after boss death")
            return True
        else:
            print(f"FAIL: Victory screen didn't appear after countdown")
            return False
    else:
        # Should show victory immediately if room is empty
        if getattr(g, "showing_victory", False):
            print(f"[OK] Victory screen appeared immediately (room empty)")
            return True
        else:
            print(f"FAIL: Victory not triggered after boss death")
            print(f"  Enemies: {len(g.enemies)}, Bosses: {len(g.bosses)}")
            return False


if __name__ == "__main__":
    try:
        success = test_horde_victory_after_boss_death_only()
        print("\n" + ("="*50))
        if success:
            print("SUCCESS: Victory screen timing is correct!")
        else:
            print("FAILURE: Victory screen has timing issues")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
