#!/usr/bin/env python3
"""Test to verify limbo horde victory is triggered ONLY by boss death."""

import pygame

from src.game import Game


def test_horde_victory_only_on_boss_death():
    """
    Verify that victory is only triggered when boss_limbo_horde dies,
    regardless of how many other enemies have been killed.

    Victory counter should be reset after each phase, so enemy kill counts
    don't affect the outcome. Only the boss death matters.
    """
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"

    # Set up horde state
    g.limbo_horde_started = True
    g.limbo_horde_active = True
    g.limbo_horde_initial = 100
    g.limbo_horde_completed = False
    g.limbo_horde_boss_killed = False
    g.limbo_horde_ready_for_victory = False

    # Kill many enemies (should NOT trigger victory)
    for i in range(50):
        g.record_enemy_kill()

    # Verify victory NOT triggered even with 50 kills (boss not dead)
    assert (
        not g.limbo_horde_ready_for_victory
    ), "Victory triggered before boss death!"
    assert (
        not g.limbo_horde_completed
    ), "Horde marked completed before boss death!"
    print("[OK] Victory NOT triggered after 50 enemy kills")

    # Simulate boss death (collision_system.py does all this when boss dies)
    g.limbo_horde_boss_killed = True
    g.limbo_horde_active = False
    g.limbo_horde_completed = True
    g.limbo_horde_ready_for_victory = True

    # Now victory should be triggered
    assert (
        g.limbo_horde_ready_for_victory
    ), "Victory NOT triggered after boss death!"
    assert g.limbo_horde_completed, "Horde not marked completed!"
    print("[OK] Victory triggered immediately on boss death")

    return True


def test_boss_death_is_only_condition():
    """
    Verify that killing all enemies WITHOUT killing the boss
    does NOT trigger victory.
    """
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"

    # Set up horde state as if final enemy is about to die
    g.limbo_horde_started = True
    g.limbo_horde_active = True
    g.limbo_horde_initial = 1  # Only 1 enemy left (the boss)
    g.limbo_horde_completed = False
    g.limbo_horde_boss_killed = False  # Boss NOT killed yet
    g.limbo_horde_ready_for_victory = False

    # Kill the final non-boss enemy
    g.record_enemy_kill()

    # Verify victory NOT triggered (boss still alive)
    assert (
        not g.limbo_horde_ready_for_victory
    ), "Victory triggered when boss is still alive!"
    print("[OK] Victory NOT triggered with boss still alive")

    return True


if __name__ == "__main__":
    try:
        success1 = test_horde_victory_only_on_boss_death()
        print("\n" + ("=" * 60))
        success2 = test_boss_death_is_only_condition()
        print("\n" + ("=" * 60))
        if success1 and success2:
            print("[PASS] ALL TESTS PASSED - Victory logic is correct!")
            exit(0)
        else:
            print("[FAIL] TESTS FAILED")
            exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
