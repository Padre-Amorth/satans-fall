#!/usr/bin/env python3
"""Test to verify double-counting issue during limbo horde."""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Suppress pygame output
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from game.core import Game

def test_limbo_horde_kill_count():
    """Verify that each enemy kill increments the counter exactly once."""
    g = Game(debug=False)
    g.fps = 60

    # Start a limbo game
    g.selected_stage = "limbo"

    # Fast-forward to horde trigger (100 frames = ~1.67 seconds, horde at ~8 seconds)
    for _ in range(500):
        g.update()

    # Check if horde started
    if not getattr(g, "limbo_horde_started", False):
        print("FAIL: Horde didn't start")
        return False

    initial_kill_count = getattr(g, "limbo_horde_killed", 0)
    print(f"Horde started. Initial kill count: {initial_kill_count}")
    print(f"Horde initial enemies: {getattr(g, 'limbo_horde_initial', 0)}")

    # Record the initial state
    initial_enemies = len(g.enemies)
    print(f"Initial enemies on screen: {initial_enemies}")

    # Fast-forward to spawn some enemies (horde phases spawn at: 0, 5s, 10s, 20s, 25s, 28s, 33s, 38s, 48s)
    for _ in range(300):  # Run 5 seconds worth of frames
        g.update()

    spawned_enemies = len(g.enemies)
    print(f"Enemies after 5 seconds: {spawned_enemies}")

    # Kill all visible enemies by removing them manually and tracking kill count
    kill_count_before = getattr(g, "limbo_horde_killed", 0)

    # Kill each enemy one at a time and verify counter increments correctly
    for i, enemy in enumerate(list(g.enemies)):
        enemy.health = 0
        g.update()
        kill_count_after = getattr(g, "limbo_horde_killed", 0)
        increment = kill_count_after - kill_count_before
        if increment != 1:
            print(f"FAIL: Enemy {i} incremented kill count by {increment}, expected 1")
            print(f"  Kill count before: {kill_count_before}, after: {kill_count_after}")
            return False
        kill_count_before = kill_count_after

    print(f"SUCCESS: Each enemy kill incremented counter exactly once")
    return True

if __name__ == "__main__":
    try:
        success = test_limbo_horde_kill_count()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
