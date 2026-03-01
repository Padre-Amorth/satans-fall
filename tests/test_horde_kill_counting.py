#!/usr/bin/env python3
"""Test to verify horde kill counter doesn't double-count enemies."""

import pygame

from src.entities.enemy import Enemy
from src.game import Game


def test_horde_kill_count_no_duplicates():
    """Verify record_enemy_kill is called only once per enemy, not duplicated."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"

    # Manually set up horde state
    g.limbo_horde_initial = 100
    g.limbo_horde_killed = 0
    g.limbo_horde_completed = False

    # Create some test enemies
    enemies = [Enemy(x=100 + i * 50, y=100, enemy_type="normal") for i in range(10)]
    for enemy in enemies:
        g.enemies.add(enemy)

    initial_kill_count = g.limbo_horde_killed
    print(f"Initial kill count: {initial_kill_count}")

    # Record kills for each enemy
    for i, enemy in enumerate(enemies):
        g.record_enemy_kill()
        expected = initial_kill_count + i + 1
        actual = g.limbo_horde_killed
        print(f"  Enemy {i}: expected={expected}, actual={actual}")
        assert (
            actual == expected
        ), f"Kill count mismatch for enemy {i}: expected {expected}, got {actual}"

    final_kill_count = g.limbo_horde_killed
    assert (
        final_kill_count == initial_kill_count + 10
    ), f"Expected +10 kills, got {final_kill_count - initial_kill_count}"
    print(f"[OK] Final kill count: {final_kill_count} (correct +10)")

    return True


def test_horde_victory_only_with_boss():
    """Verify victory is only triggered when boss is killed."""
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"

    # Set up horde state
    g.limbo_horde_initial = 11  # 10 enemies + 1 boss
    g.limbo_horde_killed = 0
    g.limbo_horde_completed = False
    g.limbo_horde_boss_killed = False
    g.limbo_horde_ready_for_victory = False

    # Kill 10 enemies (all but boss)
    for i in range(10):
        g.record_enemy_kill()

    # Verify victory NOT triggered (boss not dead)
    assert not g.limbo_horde_ready_for_victory, "Victory triggered before boss death!"
    print("[OK] Victory NOT triggered after 10 kills (boss alive)")

    # Now kill the boss (set flag and record the kill)
    g.limbo_horde_boss_killed = True
    g.record_enemy_kill()

    # Now victory should be triggered
    assert g.limbo_horde_ready_for_victory, "Victory NOT triggered after boss death!"
    assert g.limbo_horde_completed, "Horde not marked completed!"
    print("[OK] Victory triggered after boss death (kill #11)")

    return True


if __name__ == "__main__":
    try:
        success1 = test_horde_kill_count_no_duplicates()
        print("\n" + ("=" * 60))
        success2 = test_horde_victory_only_with_boss()
        print("\n" + ("=" * 60))
        if success1 and success2:
            print("[PASS] ALL TESTS PASSED - Horde kill counting is correct!")
            exit(0)
        else:
            print("[FAIL] TESTS FAILED")
            exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
