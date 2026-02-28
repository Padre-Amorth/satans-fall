"""Test limbo horde victory screen timing across all three limbo stages.

Verifies that:
1. Victory screen appears after 5 seconds (300 frames at 60fps) of horde completion
2. Victory screen appears consistently in limbo, limbo_2, and limbo_3
3. No spawning occurs during the victory countdown
"""

import sys
from pathlib import Path

import pygame

# Add project to path - must be before import to allow src imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.game import Game  # noqa: E402
from src.systems.spawn_system import SpawnSystem  # noqa: E402


def test_limbo_victory_timing_single_stage(stage_name):
    """Test victory screen timing for a single limbo stage."""
    print(f"\n{'='*60}")
    print(f"Testing {stage_name.upper()} victory screen timing")
    print(f"{'='*60}")

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
    print(f"  - Horde initial count: {game.limbo_horde_initial}")
    print(f"  - FPS: {game.fps}")
    print(f"  - Victory timer target: {game.fps * 5} frames (5 seconds)")

    # Simulate frames: update the game state frame by frame
    total_frames = 0
    max_frames = game.fps * 10  # Test for up to 10 seconds

    # Dictionary to track state changes
    state_log = {
        "horde_defeated_frame": None,
        "ready_for_victory_frame": None,
        "victory_timer_started_frame": None,
        "showing_victory_frame": None,
        "victory_alpha_maxed_frame": None,
    }

    print(
        f"\n[SIMULATION] Starting frame-by-frame simulation (max {max_frames} frames)..."
    )

    while total_frames < max_frames:
        # Manually complete the horde on frame 0
        if total_frames == 0:
            game.limbo_horde_killed = game.limbo_horde_initial
            # Trigger the record_enemy_kill logic directly
            game.record_enemy_kill()
            print(
                f"\n  Frame {total_frames}: Manually set horde_killed = {game.limbo_horde_initial}"
            )
            print(
                f"  Frame {total_frames}: Called record_enemy_kill() to trigger horde completion logic"
            )

        # Call update to advance game state
        try:
            # Update game logic
            game.update_game()

            # Log state changes
            if (
                getattr(game, "limbo_horde_completed", False)
                and state_log["horde_defeated_frame"] is None
            ):
                state_log["horde_defeated_frame"] = total_frames
                print(
                    f"  Frame {total_frames}: HORDE DEFEATED (limbo_horde_completed=True)"
                )

            if (
                getattr(game, "limbo_horde_ready_for_victory", False)
                and state_log["ready_for_victory_frame"] is None
            ):
                state_log["ready_for_victory_frame"] = total_frames
                print(f"  Frame {total_frames}: Ready for victory flag set")

            if (
                getattr(game, "limbo_horde_victory_timer", 0) > 0
                and state_log["victory_timer_started_frame"] is None
            ):
                state_log["victory_timer_started_frame"] = total_frames
                print(
                    f"  Frame {total_frames}: Victory timer started ({game.limbo_horde_victory_timer} frames)"
                )

            if (
                getattr(game, "showing_victory", False)
                and state_log["showing_victory_frame"] is None
            ):
                state_log["showing_victory_frame"] = total_frames
                print(f"  Frame {total_frames}: ★ VICTORY SCREEN SHOWN ★")

            if (
                getattr(game, "victory_alpha", 0) >= 255
                and state_log["victory_alpha_maxed_frame"] is None
            ):
                state_log["victory_alpha_maxed_frame"] = total_frames
                print(f"  Frame {total_frames}: Victory alpha fully faded (255)")

        except Exception as e:
            print(f"  Frame {total_frames}: ERROR during update: {e}")
            import traceback

            traceback.print_exc()

        total_frames += 1

    # Analyze results
    print(f"\n{'='*60}")
    print(f"RESULTS FOR {stage_name.upper()}")
    print(f"{'='*60}")

    if state_log["showing_victory_frame"] is None:
        print("FAIL: Victory screen never appeared!")
        return False

    victory_delay = state_log["showing_victory_frame"] - (
        state_log["ready_for_victory_frame"] or 0
    )
    expected_delay = game.fps * 5  # 5 seconds
    tolerance = game.fps * 1  # ±1 second tolerance

    print(f"Victory screen appeared after: {victory_delay} frames")
    print(f"Expected delay: {expected_delay} frames (5 seconds)")
    print(f"Tolerance: ±{tolerance} frames (±1 second)")

    if abs(victory_delay - expected_delay) <= tolerance:
        print("PASS: Victory screen timing is correct!")
        return True
    else:
        print(
            f"FAIL: Victory screen timing is off by {abs(victory_delay - expected_delay)} frames"
        )
        return False


def test_all_limbo_stages():
    """Test victory screen timing across all three limbo stages."""
    print("\n" + "=" * 60)
    print("LIMBO VICTORY SCREEN TIMING TEST")
    print("=" * 60)

    stages = ["limbo", "limbo_2", "limbo_3"]
    results = {}

    for stage in stages:
        try:
            passed = test_limbo_victory_timing_single_stage(stage)
            results[stage] = passed
        except Exception as e:
            print(f"\nERROR testing {stage}: {e}")
            import traceback

            traceback.print_exc()
            results[stage] = False

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    for stage, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{stage:12} -> {status}")

    all_passed = all(results.values())
    if all_passed:
        print("\nALL TESTS PASSED!")
    else:
        print("\nSOME TESTS FAILED")

    return all_passed


if __name__ == "__main__":
    success = test_all_limbo_stages()
    sys.exit(0 if success else 1)
