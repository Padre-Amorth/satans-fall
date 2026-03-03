#!/usr/bin/env python3
"""Regression test: boss_limbo_horde must NOT be removed from the sprite group
by collision_system when killed. Only game.update() should handle cleanup.

Previous bug: collision_system called boss.kill() which removed the boss from
the bosses group BEFORE game.update() could detect the death. The victory
countdown never started and the level continued infinitely.

This test verifies the full flow:
1. Boss dies (health set to 0)
2. Collision system processes the dead boss but does NOT remove it
3. game.update() detects the dead boss, sets victory flags, clears groups
4. Victory countdown runs for 5 seconds and victory screen appears
"""

import os
import sys

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from src.game import Game


def test_boss_not_removed_by_collision_system():
    """Verify collision system does not call kill() on boss_limbo_horde."""
    g = Game(debug=True)
    g.fps = 60
    g.selected_stage = "limbo"

    # Set up horde state
    g.limbo_horde_started = True
    g.limbo_horde_active = True
    g.limbo_horde_completed = False
    g.limbo_horde_boss_killed = False
    g.limbo_horde_ready_for_victory = False
    g.limbo_horde_victory_timer = 0

    # Spawn the horde boss
    g.spawn_system.spawn_boss("limbo_horde")
    if not g.bosses:
        print("FAIL: Boss didn't spawn")
        return False

    boss = list(g.bosses)[0]
    print(f"[OK] Boss spawned: type={boss.enemy_type}, health={boss.health}")

    # Kill the boss
    boss.health = 0
    print("[OK] Boss health set to 0")

    # Verify boss is still in the group (this is the key regression check)
    if boss not in g.bosses:
        print("FAIL: Boss removed from group before update! (regression)")
        return False
    print(f"[OK] Boss still in bosses group (count={len(g.bosses)})")

    # Run game.update() — this should detect the dead boss and set victory flags
    g.update()

    completed = getattr(g, "limbo_horde_completed", False)
    timer = getattr(g, "limbo_horde_victory_timer", 0)
    print(f"  After update: completed={completed}, timer={timer}")

    if not completed:
        print("FAIL: Horde not marked completed after boss death!")
        return False
    print("[OK] Horde marked completed by game.update()")

    if timer < 290 or timer > 300:
        print(f"FAIL: Timer should be ~300 frames, got {timer}")
        return False
    print(f"[OK] Victory countdown started: {timer} frames (5 seconds)")

    # Boss should now be removed from group by game.update()
    if len(g.bosses) > 0:
        print("FAIL: Boss should be cleared from group after update!")
        return False
    print("[OK] Boss cleared from group by game.update()")

    # Fast-forward through countdown to victory screen
    for _ in range(timer + 5):
        g.update()

    if not getattr(g, "showing_victory", False):
        print("FAIL: Victory screen not shown after countdown!")
        return False
    print("[OK] Victory screen appeared (SATANIC VICTORY)")

    return True


def test_full_update_cycle_triggers_victory():
    """Run full update() cycles after boss death — simulates real gameplay.

    In real gameplay, collision_system.handle_collisions() runs as part of
    update(). This test sets boss health to 0 then runs update() repeatedly,
    verifying that the collision system's fallback dead-boss loop does NOT
    remove boss_limbo_horde from the group before the detection code runs.
    """
    g = Game(debug=True)
    g.fps = 60
    g.selected_stage = "limbo"

    g.limbo_horde_started = True
    g.limbo_horde_active = True
    g.limbo_horde_completed = False
    g.limbo_horde_boss_killed = False
    g.limbo_horde_ready_for_victory = False
    g.limbo_horde_victory_timer = 0

    g.spawn_system.spawn_boss("limbo_horde")
    if not g.bosses:
        print("FAIL: Boss didn't spawn")
        return False

    boss = list(g.bosses)[0]
    boss.health = 0
    print("[OK] Boss killed (health=0)")

    # Run update multiple times — each call includes collision_system internally
    victory_appeared = False
    for frame in range(400):
        g.update()

        if getattr(g, "showing_victory", False):
            print(f"[OK] Victory screen appeared at frame {frame}")
            victory_appeared = True
            break

    if not victory_appeared:
        print("FAIL: Victory screen never appeared after 400 frames!")
        return False

    # Should appear around frame 300 (5 seconds at 60fps)
    if frame < 280 or frame > 320:
        print(f"WARNING: Victory appeared at unexpected frame {frame} (expected ~300)")

    return True


if __name__ == "__main__":
    try:
        results = []

        print("=" * 60)
        print("TEST 1: Boss not removed by collision system")
        print("=" * 60)
        results.append(test_boss_not_removed_by_collision_system())

        print()
        print("=" * 60)
        print("TEST 2: Full update cycle triggers victory")
        print("=" * 60)
        results.append(test_full_update_cycle_triggers_victory())

        print()
        print("=" * 60)
        if all(results):
            print("SUCCESS: All regression tests passed!")
            sys.exit(0)
        else:
            failed = sum(1 for r in results if not r)
            print(f"FAILURE: {failed}/{len(results)} tests failed")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
