"""Test crusader spawning across all stages."""

import pygame

from src.game import Game


def test_crusader_purgatory_visibility():
    """Test that crusaders spawn with reasonable frequency in Purgatory."""
    pygame.init()
    g = Game(debug=True)
    ss = g.spawn_system

    # Test Purgatory
    g.selected_stage = "purgatory"
    g.wave = 2  # must be wave 2+ to allow crusaders
    ss.crusader_spawned_this_wave = 0

    # Spawn 1000 enemies (statistically should see crusaders)
    for _ in range(1000):
        ss.spawn_enemy()

    print(f"[Purgatory] Crusaders spawned: {ss.crusader_spawned_this_wave}")
    # With 1.5% chance and 5 limit, expecting at least 2+ spawns out of 1000
    assert (
        ss.crusader_spawned_this_wave >= 2
    ), "Expected at least 2 crusaders in Purgatory with 1.5% chance"


def test_crusader_hell_visibility():
    """Test that crusaders spawn with reasonable frequency in Hell."""
    pygame.init()
    g = Game(debug=True)
    ss = g.spawn_system

    g.selected_stage = "hell"
    g.wave = 2  # must be wave 2+ to allow crusaders
    ss.crusader_spawned_this_wave = 0

    for _ in range(1000):
        ss.spawn_enemy()

    print(f"[Hell] Crusaders spawned: {ss.crusader_spawned_this_wave}")
    assert (
        ss.crusader_spawned_this_wave >= 2
    ), "Expected at least 2 crusaders in Hell with 1.5% chance"


def test_crusader_limbo_should_be_zero():
    """Crusaders should NOT spawn in Limbo stages."""
    pygame.init()
    g = Game(debug=True)
    ss = g.spawn_system

    for stage in ["limbo", "limbo_2", "limbo_3", "limbo_final"]:
        g.selected_stage = stage
        ss.crusader_spawned_this_wave = 0

        # Even with 500 spawns, should be zero (allowed check is False)
        for _ in range(500):
            ss.spawn_enemy()

        print(f"[{stage}] Crusaders spawned: {ss.crusader_spawned_this_wave}")
        assert (
            ss.crusader_spawned_this_wave == 0
        ), f"Crusaders should not spawn in {stage}"


def test_crusader_limit_enforced_all_stages():
    """Test that 5-per-wave limit is enforced."""
    pygame.init()
    g = Game(debug=True)
    ss = g.spawn_system

    for stage in ["purgatory", "hell"]:
        g.selected_stage = stage
        g.wave = 2  # must be wave 2+ to allow crusaders
        ss.crusader_spawned_this_wave = 0

        # Try to force spawns by setting high probability
        for _ in range(2000):
            ss.spawn_enemy()

        print(f"[{stage}] Max crusaders in wave: {ss.crusader_spawned_this_wave}")
        assert ss.crusader_spawned_this_wave <= 5, f"Crusader limit exceeded in {stage}"


def test_crusader_counter_reset_per_wave():
    """Test that crusader counter resets on wave progression."""
    pygame.init()
    g = Game(debug=True)
    ss = g.spawn_system
    g.selected_stage = "purgatory"

    ss.crusader_spawned_this_wave = 3

    # Trigger wave progression
    g.wave_time = g.wave_duration
    ss.update_wave_progression()

    print(f"[Wave Reset] Crusaders after reset: {ss.crusader_spawned_this_wave}")
    assert ss.crusader_spawned_this_wave == 0, "Crusader counter should reset each wave"


if __name__ == "__main__":
    test_crusader_purgatory_visibility()
    test_crusader_hell_visibility()
    test_crusader_limbo_should_be_zero()
    test_crusader_limit_enforced_all_stages()
    test_crusader_counter_reset_per_wave()
    print("\n✅ All crusader spawn tests passed!")
