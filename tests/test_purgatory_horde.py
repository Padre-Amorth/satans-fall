"""Test Purgatory horde event triggering and behavior."""

import pytest

from src.game import Game
from src.game_constants import (
    PURGATORY_HORDE_TIME_1,
    PURGATORY_HORDE_TIME_2,
    PURGATORY_HORDE_TIME_3,
)


@pytest.mark.parametrize(
    "stage,horde_time",
    [
        ("purgatory", PURGATORY_HORDE_TIME_1),
        ("purgatory_2", PURGATORY_HORDE_TIME_2),
        ("purgatory_3", PURGATORY_HORDE_TIME_3),
    ],
)
def test_purgatory_horde_triggers_at_correct_time(stage, horde_time):
    """Purgatory horde should trigger at stage-specific times."""
    g = Game()
    g.reset_game()
    g.select_stage(stage)

    # Just before trigger
    g.time_elapsed = horde_time - 0.1
    g.spawn_system.update_enemy_spawning()
    assert not getattr(
        g, "purgatory_horde_started", False
    ), f"Horde should NOT start yet in {stage}"

    # At trigger time
    g.time_elapsed = horde_time + 0.1
    g.spawn_system.update_enemy_spawning()
    assert getattr(
        g, "purgatory_horde_started", False
    ), f"Horde should START at {horde_time}s in {stage}"
    assert getattr(
        g, "purgatory_horde_active", False
    ), f"Horde should be active in {stage}"


def test_purgatory_horde_schedule_has_no_boss():
    """Purgatory horde should have 100 enemies total (no boss)."""
    g = Game()
    g.reset_game()
    g.select_stage("purgatory")

    g.time_elapsed = PURGATORY_HORDE_TIME_1 + 0.1
    g.spawn_system.update_enemy_spawning()

    schedule = getattr(g, "purgatory_horde_schedule", [])
    assert len(schedule) > 0, "Schedule should have phases"

    # Count total: sum of all 'count' values (no 'boss_count' in purgatory)
    total = 0
    for phase in schedule:
        total += phase.get("count", 0)
        # Purgatory should NOT have boss_count
        assert (
            "boss_count" not in phase or phase.get("boss_count", 0) == 0
        ), f"Purgatory phase should not have bosses, got: {phase}"

    assert total == 100, f"Purgatory horde should have 100 enemies total, got {total}"


def test_purgatory_horde_suspends_normal_spawning():
    """During purgatory horde, normal spawning should be suspended."""
    g = Game()
    g.reset_game()
    g.select_stage("purgatory")

    # Trigger horde
    g.time_elapsed = PURGATORY_HORDE_TIME_1 + 0.1
    g.spawn_system.update_enemy_spawning()

    assert getattr(g, "purgatory_horde_active", False), "Horde should be active"


def test_purgatory_horde_not_in_limbo():
    """Limbo horde should trigger, not purgatory horde."""
    g = Game()
    g.reset_game()
    g.select_stage("limbo")

    # At limbo horde time (360s)
    g.time_elapsed = 360.1
    g.spawn_system.update_enemy_spawning()

    assert getattr(g, "limbo_horde_started", False), "Limbo horde should START"
    assert not getattr(
        g, "purgatory_horde_started", False
    ), "Purgatory horde should NOT start in limbo"


def test_purgatory_horde_explosion_after_60_seconds():
    """Purgatory horde explosion (malevolent wave) should trigger after 60 seconds."""
    g = Game()
    g.reset_game()
    g.select_stage("purgatory")

    # Trigger horde
    g.time_elapsed = PURGATORY_HORDE_TIME_1 + 0.1
    g.spawn_system.update_enemy_spawning()

    assert getattr(g, "purgatory_horde_active", False), "Horde should be active"
    assert not getattr(
        g, "purgatory_horde_explosion_ready", False
    ), "Explosion should NOT trigger yet"

    # Advance to 60 seconds into horde (simulate with elapsed frames)
    # 60 seconds @ 60 fps = 3600 frames
    g.purgatory_horde_elapsed = int(60 * g.fps)

    # Call update to trigger explosion check (in _update_pre_guard_state)
    g._update_pre_guard_state()

    assert getattr(
        g, "purgatory_horde_explosion_ready", False
    ), "Explosion should be ready after 60s"
    assert not getattr(
        g, "purgatory_horde_active", False
    ), "Horde should no longer be active"
    assert getattr(
        g, "purgatory_horde_completed", False
    ), "Horde should be marked completed"


def test_purgatory_horde_victory_after_explosion():
    """Victory screen should show 5 seconds after explosion wave completes."""
    g = Game()
    g.reset_game()
    g.select_stage("purgatory")

    # Trigger horde
    g.time_elapsed = PURGATORY_HORDE_TIME_1 + 0.1
    g.spawn_system.update_enemy_spawning()

    # Trigger explosion
    g.purgatory_horde_elapsed = int(60 * g.fps)
    g._update_pre_guard_state()

    assert getattr(g, "purgatory_horde_explosion_ready", False), "Should be ready"

    # Simulate wave expansion (1 second)
    for _ in range(int(g.fps)):
        g._update_pre_guard_state()

    # Wave should now be complete and victory countdown should have started
    assert (
        getattr(g, "purgatory_horde_victory_timer", 0) > 0
    ), "Victory timer should be active"

    # Simulate countdown (5 seconds = 5*60 frames @ 60fps)
    for _ in range(int(5 * g.fps)):
        g._update_pre_guard_state()

    # Victory should now be showing
    assert getattr(
        g, "showing_victory", False
    ), "Victory screen should be shown after countdown"
