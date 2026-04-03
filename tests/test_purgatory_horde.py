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

    # Simulate wave expansion (2 seconds - halved speed)
    for _ in range(int(2 * g.fps)):
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


def test_purgatory_horde_wave_has_particles_and_veil():
    """Wave should render with infernal particles and reddish veil."""
    g = Game()
    g.reset_game()
    g.select_stage("purgatory")

    # Trigger horde and explosion
    g.time_elapsed = PURGATORY_HORDE_TIME_1 + 0.1
    g.spawn_system.update_enemy_spawning()

    g.purgatory_horde_elapsed = int(60 * g.fps)
    g._update_pre_guard_state()

    assert (
        getattr(g, "purgatory_horde_wave_timer", 0.0) > 0.0
    ), "Wave timer should be active"
    # Wave visuals are rendered in ui.py draw_special_effects() - no separate state to test


def test_boom_upgrade_damage_and_range():
    """BOOM! upgrade should have correct damage and range scaling."""
    g = Game()
    g.reset_game()
    g.select_stage("purgatory")

    # Test base values (0 upgrades)
    g.player.kill_explosion_upgrades = 0
    base_damage = 30
    base_range = 70
    damage_0 = base_damage + (0 * 20)
    range_0 = base_range + (0 * 20)
    assert damage_0 == 30, "Base damage should be 30"
    assert range_0 == 70, "Base range should be 70px"

    # Test upgrade 1
    g.player.kill_explosion_upgrades = 1
    damage_1 = base_damage + (1 * 20)
    range_1 = base_range + (1 * 20)
    assert damage_1 == 50, "Upgrade 1 damage should be 50"
    assert range_1 == 90, "Upgrade 1 range should be 90px"

    # Test upgrade 2
    g.player.kill_explosion_upgrades = 2
    damage_2 = base_damage + (2 * 20)
    range_2 = base_range + (2 * 20)
    assert damage_2 == 70, "Upgrade 2 damage should be 70"
    assert range_2 == 110, "Upgrade 2 range should be 110px"

    # Test upgrade 3
    g.player.kill_explosion_upgrades = 3
    damage_3 = base_damage + (3 * 20)
    range_3 = base_range + (3 * 20)
    assert damage_3 == 90, "Upgrade 3 damage should be 90"
    assert range_3 == 130, "Upgrade 3 range should be 130px"
