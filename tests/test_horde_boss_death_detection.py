#!/usr/bin/env python3
"""Test that boss death is detected in update loop and triggers victory countdown."""

import os
import sys

# Suppress pygame output
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from src.game import Game


def test_boss_death_triggers_victory():
    """
    Verify that killing the boss (by setting health=0) automatically triggers
    the victory countdown, without needing collision system involvement.
    """
    g = Game(debug=True)
    g.fps = 60

    # Start a limbo game
    g.selected_stage = "limbo"

    # Manually set horde state
    g.limbo_horde_started = True
    g.limbo_horde_active = True
    g.limbo_horde_completed = False
    g.limbo_horde_boss_killed = False
    g.limbo_horde_ready_for_victory = False

    print("[OK] Horde manually started")

    # Manually spawn the horde boss
    g.spawn_system.spawn_boss("limbo_horde")

    if not g.bosses:
        print("FAIL: Boss didn't spawn")
        return False

    boss = list(g.bosses)[0]
    print(f"[OK] Boss spawned with {boss.health} health")

    # Kill the boss by just setting health = 0 (no collision)
    boss.health = 0
    print("[OK] Boss health set to 0")

    # Call update() which should detect the dead boss and trigger victory setup
    g.update()
    print("[OK] Update called after boss death")

    # Check if victory was triggered
    ready_for_victory = getattr(g, "limbo_horde_ready_for_victory", False)
    completed = getattr(g, "limbo_horde_completed", False)
    timer = getattr(g, "limbo_horde_victory_timer", 0)

    print(f"  ready_for_victory={ready_for_victory}, completed={completed}")
    print(f"  timer={timer} frames")

    if not completed:
        print("FAIL: Horde not marked completed after boss death!")
        return False

    print("[OK] Horde marked completed")

    if timer < 290 or timer > 300:
        print(f"FAIL: Timer should be around 300, got {timer}")
        return False

    print(f"[OK] Victory countdown started with {timer} frames")

    # Now fast-forward through the countdown
    for _ in range(timer + 5):
        g.update()

    if not getattr(g, "showing_victory", False):
        print("FAIL: Victory screen not shown after countdown!")
        return False

    print("[OK] Victory screen appeared!")
    return True


if __name__ == "__main__":
    try:
        success = test_boss_death_triggers_victory()
        print("\n" + ("=" * 60))
        if success:
            print("SUCCESS: Boss death detection works correctly!")
            sys.exit(0)
        else:
            print("FAILURE: Boss death detection failed")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
