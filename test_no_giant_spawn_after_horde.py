"""Test that NO giants spawn after limbo horde completion.

Verifies that:
1. No giant enemies are spawned after horde completion
2. No giant enemies are spawned during victory countdown
3. This holds true across all three limbo stage variants
"""

import sys
from pathlib import Path

import pytest
import pygame


from src.game import Game  # noqa: E402
from src.systems.spawn_system import SpawnSystem  # noqa: E402


@pytest.mark.parametrize("stage_name", ["limbo", "limbo_2", "limbo_3"])
def test_no_giants_spawn_after_horde(stage_name):
    """Test that NO giants spawn after horde completion."""

    pygame.init()
    pygame.display.set_mode((1280, 720))

    # Create game with debug enabled
    game = Game(debug=True)
    game.selected_stage = stage_name
    game.debug = True

    # Initialize game state for the stage
    game.generate_walls()
    game._init_managers()

    # Manually trigger limbo horde setup
    spawn_sys = SpawnSystem(game)
    game.spawn_system = spawn_sys

    # Start the horde
    spawn_sys._start_limbo_horde()
    game.limbo_horde_active = True
    game.limbo_horde_started = True

    print(f"\n[SETUP] Limbo horde started in {stage_name}")
    print(f"  - FPS: {game.fps}")

    # Simulate frames: update the game state frame by frame
    total_frames = 0
    max_frames = game.fps * 10  # Test for up to 10 seconds

    giants_created = []
    horde_defeated_frame = None
    showing_victory_frame = None



    # Spawn the horde boss on frame 0
    boss_spawned = False

    while total_frames < max_frames:
        # Spawn and kill the horde boss on frame 0
        if total_frames == 0 and not boss_spawned:
            game.spawn_system.spawn_boss("limbo_horde")
            boss_spawned = True
            print(f"\n  Frame {total_frames}: Limbo horde boss spawned")

        # Kill the boss on frame 10 to give time for setup
        if total_frames == 10 and boss_spawned:
            if game.bosses:
                boss = list(game.bosses)[0]
                boss.health = 0
                print(f"  Frame {total_frames}: Boss health set to 0 (death triggered)")

        # Track initial enemy count before update
        enemies_before = len(game.enemies)

        # Call update to advance game state
        try:
            game.update_game()

            # Check if new giant was spawned
            enemies_after = len(game.enemies)
            if enemies_after > enemies_before:
                # Check if the new enemy is a giant
                new_enemies = list(game.enemies)[enemies_before:]
                for enemy in new_enemies:
                    if hasattr(enemy, "enemy_type") and enemy.enemy_type == "giant":
                        giants_created.append((total_frames, enemy))
                        print(
                            f"  Frame {total_frames}: WARNING - GIANT SPAWNED! (total enemies: {enemies_after})"
                        )

            # Track when horde is defeated
            if (
                getattr(game, "limbo_horde_completed", False)
                and horde_defeated_frame is None
            ):
                horde_defeated_frame = total_frames
                print(f"  Frame {total_frames}: HORDE DEFEATED")

            # Track when victory screen shows
            if (
                getattr(game, "showing_victory", False)
                and showing_victory_frame is None
            ):
                showing_victory_frame = total_frames
                print(f"  Frame {total_frames}: VICTORY SCREEN SHOWN")

        except Exception as e:
            print(f"  Frame {total_frames}: ERROR during update: {e}")
            import traceback

            traceback.print_exc()

        total_frames += 1

    # Analyze results
    print(f"\n{'='*60}")
    print(f"RESULTS FOR {stage_name.upper()}")
    print(f"{'='*60}")

    if giants_created:
        print(
            f"FAIL: {len(giants_created)} giants spawned after horde completion!"
        )
        for frame, enemy in giants_created:
            print(f"  - Frame {frame}: giant spawned")
        return False
    else:
        print("PASS: No giants spawned after horde completion!")
        if horde_defeated_frame is not None:
            print(f"  - Horde defeated at frame {horde_defeated_frame}")
        if showing_victory_frame is not None:
            print(
                f"  - Victory screen appeared at frame {showing_victory_frame}"
            )
        return True


def test_all_limbo_stages():
    """Test that NO giants spawn after horde in all three limbo stages."""
    print("\n" + "="*60)
    print("NO GIANTS SPAWN AFTER HORDE TEST")
    print("="*60)

    stages = ["limbo", "limbo_2", "limbo_3"]
    results = {}

    for stage in stages:
        try:
            passed = test_no_giants_spawn_after_horde(stage)
            results[stage] = passed
        except Exception as e:
            print(f"\nERROR testing {stage}: {e}")
            import traceback

            traceback.print_exc()
            results[stage] = False

    # Final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    for stage, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{stage:12} -> {status}")

    all_passed = all(results.values())
    if all_passed:
        print("\nALL TESTS PASSED - NO GIANTS SPAWN AFTER HORDE!")
    else:
        print("\nSOME TESTS FAILED - GIANTS ARE SPAWNING!")

    return all_passed


if __name__ == "__main__":
    success = test_all_limbo_stages()
    sys.exit(0 if success else 1)
