#!/usr/bin/env python3
"""Test horde victory with stage-specific timing for limbo variants.

Verifies that the victory condition (boss death) works correctly
at the correct spawn times for each limbo stage:
- limbo: 360s (6 minutes)
- limbo_2: 420s (7 minutes)
- limbo_3: 480s (8 minutes)
"""

import os

import pygame
import pytest

# Suppress pygame output
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from src.game import Game
from src.game_constants import (
    LIMBO_HORDE_TIME_1,
    LIMBO_HORDE_TIME_2,
    LIMBO_HORDE_TIME_3,
)


@pytest.mark.parametrize(
    "stage,horde_time",
    [
        ("limbo", LIMBO_HORDE_TIME_1),
        ("limbo_2", LIMBO_HORDE_TIME_2),
        ("limbo_3", LIMBO_HORDE_TIME_3),
    ],
)
def test_boss_death_triggers_victory_with_stage_timing(stage, horde_time):
    """Verify boss death triggers victory at correct stage-specific timing.

    Tests that when the boss is killed at the correct horde spawn time
    for each limbo stage, the victory countdown begins immediately.
    """
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = stage

    # Fast-forward to the horde spawn time
    g.time_elapsed = horde_time
    g.spawn_system.update_enemy_spawning()

    # Verify horde was triggered
    assert getattr(
        g, "limbo_horde_started", False
    ), f"Horde not started at {horde_time}s for {stage}"

    # Verify horde is active (required for victory detection)
    assert getattr(g, "limbo_horde_active", False), f"Horde not active on {stage}"

    # Manually spawn the boss (since we fast-forwarded)
    # Use 'limbo_horde' not 'boss_limbo_horde' - that's the enemy_type,
    # not the spawn type that enemy_manager expects
    g.spawn_system.spawn_boss("limbo_horde")
    assert g.bosses, f"Boss failed to spawn on {stage}"

    boss = list(g.bosses)[0]
    initial_health = boss.health
    assert initial_health > 0, "Boss should spawn with health > 0"
    # Verify it's the correct type
    assert (
        getattr(boss, "enemy_type", None) == "boss_limbo_horde"
    ), f"Expected boss_limbo_horde, got {getattr(boss, 'enemy_type', None)}"

    # Kill the boss
    boss.health = 0

    # Update to trigger victory detection
    g.update()

    # Verify victory was triggered
    assert getattr(
        g, "limbo_horde_completed", False
    ), f"Horde not marked completed on {stage} after boss death"

    # Verify countdown was started (should be ~300 frames)
    # Note: limbo_horde_ready_for_victory is consumed after timer starts,
    # so we only check the victory_timer itself
    timer = getattr(g, "limbo_horde_victory_timer", 0)
    assert (
        290 <= timer <= 310
    ), f"Victory timer invalid on {stage}: {timer} (expected ~300)"


@pytest.mark.parametrize(
    "stage,horde_time",
    [
        ("limbo", LIMBO_HORDE_TIME_1),
        ("limbo_2", LIMBO_HORDE_TIME_2),
        ("limbo_3", LIMBO_HORDE_TIME_3),
    ],
)
def test_victory_screen_appears_after_boss_death(stage, horde_time):
    """Verify victory screen appears after countdown completes.

    Tests that the victory overlay is displayed after the 5-second
    countdown following boss death.
    """
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = stage

    # Trigger horde
    g.time_elapsed = horde_time
    g.spawn_system.update_enemy_spawning()

    # Verify horde is active
    assert getattr(g, "limbo_horde_active", False), f"Horde not active on {stage}"

    # Spawn and kill boss
    g.spawn_system.spawn_boss("limbo_horde")
    boss = list(g.bosses)[0]
    # Verify it's the correct type
    assert (
        getattr(boss, "enemy_type", None) == "boss_limbo_horde"
    ), f"Expected boss_limbo_horde, got {getattr(boss, 'enemy_type', None)}"
    boss.health = 0

    # Trigger victory detection
    g.update()

    # Get countdown time
    timer = getattr(g, "limbo_horde_victory_timer", 0)
    assert timer > 0, f"Victory timer not started on {stage}"

    # Fast-forward through countdown
    for _ in range(timer + 10):
        g.update()

    # Verify victory screen appeared
    assert getattr(
        g, "showing_victory", False
    ), f"Victory screen not shown on {stage} after countdown"


@pytest.mark.parametrize(
    "stage,horde_time",
    [
        ("limbo", LIMBO_HORDE_TIME_1),
        ("limbo_2", LIMBO_HORDE_TIME_2),
        ("limbo_3", LIMBO_HORDE_TIME_3),
    ],
)
def test_no_victory_without_boss_death(stage, horde_time):
    """Verify victory NOT triggered if boss survives.

    Tests that killing many regular enemies does NOT trigger
    victory if the boss is still alive.
    """
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = stage

    # Trigger horde
    g.time_elapsed = horde_time
    g.spawn_system.update_enemy_spawning()

    # Verify horde is active
    assert getattr(g, "limbo_horde_active", False), f"Horde not active on {stage}"

    # Spawn boss but DON'T kill it
    g.spawn_system.spawn_boss("limbo_horde")
    boss_list = list(g.bosses)
    assert boss_list, "Boss failed to spawn"
    boss_spawned = boss_list[0]
    assert (
        getattr(boss_spawned, "enemy_type", None) == "boss_limbo_horde"
    ), f"Expected boss_limbo_horde, got {getattr(boss_spawned, 'enemy_type', None)}"

    # Simulate killing many enemies via record_enemy_kill
    for _ in range(50):
        g.record_enemy_kill()

    # Verify victory NOT triggered
    assert not getattr(
        g, "limbo_horde_completed", False
    ), f"Victory triggered without boss death on {stage}"
    assert not getattr(
        g, "limbo_horde_ready_for_victory", False
    ), f"Ready for victory without boss death on {stage}"

    # Now kill the boss
    boss = list(g.bosses)[0]
    boss.health = 0
    g.update()

    # Now victory SHOULD be triggered
    assert getattr(
        g, "limbo_horde_completed", False
    ), f"Victory not triggered after boss death on {stage}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
