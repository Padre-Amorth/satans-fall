#!/usr/bin/env python3
"""Test to verify limbo horde victory countdown starts immediately on boss death."""
import sys
import os

# Suppress pygame output
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from src.game import Game


def test_victory_countdown_on_boss_death():
    """
    Verify that:
    1. Victory countdown (limbo_horde_victory_timer) is set exactly when boss dies
    2. Victory countdown is 5 seconds (300 frames @ 60fps)
    3. Victory screen appears after countdown expires
    """
    g = Game(debug=True)
    g.fps = 60

    # Start a limbo game
    g.selected_stage = "limbo"

    # Manually set horde state to trigger spawn logic
    g.limbo_horde_started = True
    g.limbo_horde_active = True
    g.limbo_horde_completed = False
    g.limbo_horde_boss_killed = False
    g.limbo_horde_ready_for_victory = False

    print("[OK] Horde manually started")

    # Manually spawn the horde boss
    g.spawn_system.spawn_boss("limbo_horde")

    # Verify boss spawned
    if not g.bosses:
        print("FAIL: Boss didn't spawn")
        return False

    boss = list(g.bosses)[0]
    print(f"[OK] Boss spawned with {boss.health} health")

    # Get initial state before boss death
    initial_timer = getattr(g, "limbo_horde_victory_timer", 0)
    print(f"  Initial timer: {initial_timer} frames")

    # Kill the boss by simulating the collision system's boss death handler
    print(f"  Boss before death: health={boss.health}")
    boss.health = 0
    print(f"  Boss after setting health=0: health={boss.health}")

    # Manually trigger the victory setup (simulating collision system behavior)
    if boss.enemy_type == "boss_limbo_horde":
        g.limbo_horde_boss_killed = True
        g.limbo_horde_active = False
        g.limbo_horde_completed = True
        g.limbo_horde_ready_for_victory = True
        g.enemies.empty()  # Clear remaining enemies
        g.bosses.empty()  # Clear bosses (boss will be removed)
        print(f"  Manually triggered victory setup")

    # First update to process the victory countdown logic
    g.update()
    print(f"  After first update: enemies={len(g.enemies)}, bosses={len(g.bosses)}")

    # Check if victory countdown was immediately started
    timer_after_death = getattr(g, "limbo_horde_victory_timer", 0)
    ready_for_victory = getattr(g, "limbo_horde_ready_for_victory", False)
    completed = getattr(g, "limbo_horde_completed", False)
    print(f"  Timer after boss death: {timer_after_death} frames")
    print(f"  ready_for_victory={ready_for_victory}, completed={completed}")

    # The timer should be set to 5 seconds = 300 frames @ 60fps
    # Note: timer is decremented in the same update, so we expect 299 frames
    expected_timer = int(g.fps * 5) - 1
    if timer_after_death < expected_timer or timer_after_death > expected_timer + 1:
        print(f"FAIL: Timer should be around {expected_timer} frames, got {timer_after_death}")
        return False

    print(f"[OK] Victory countdown started: {timer_after_death} frames remaining (nearly 5 seconds)")

    # Verify victory screen NOT shown yet
    if getattr(g, "showing_victory", False):
        print("FAIL: Victory screen shown before countdown!")
        return False
    print(f"[OK] Victory screen NOT shown yet (countdown active)")

    # Fast-forward through the countdown
    print(f"  Counting down...")
    for i in range(timer_after_death):
        g.update()
        current_timer = getattr(g, "limbo_horde_victory_timer", 0)
        if current_timer <= 0:
            print(f"  Countdown expired at frame {i}")
            break

    # Check if victory screen is now visible
    if not getattr(g, "showing_victory", False):
        print("FAIL: Victory screen not shown after countdown!")
        return False

    print(f"[OK] Victory screen appeared after countdown!")
    return True


if __name__ == "__main__":
    try:
        success = test_victory_countdown_on_boss_death()
        print("\n" + ("=" * 60))
        if success:
            print("SUCCESS: Victory countdown works correctly!")
            sys.exit(0)
        else:
            print("FAILURE: Victory countdown has issues")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
