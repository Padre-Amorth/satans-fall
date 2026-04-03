import pygame

from src.game import Game


def test_big_enemy_timer_triggers_spawn():
    pygame.init()
    g = Game(debug=True)
    em = g.enemy_manager
    assert em is not None

    # Ensure manager timers are used
    em.big_enemy_timer = 1
    em.big_spawned_this_wave = False

    # Call the spawn update
    g.update_enemy_spawning()

    # After update, manager should have spawned a giant
    giants = [e for e in g.enemies if getattr(e, "enemy_type", "") == "giant"]
    assert len(giants) >= 1
    assert em.big_spawned_this_wave is True


def test_wave_reset_clears_manager_flag():
    pygame.init()
    g = Game(debug=True)
    em = g.enemy_manager
    assert em is not None

    # Simulate that a big spawn happened
    em.big_spawned_this_wave = True

    # Advance wave to trigger reset
    g.wave_time = g.wave_duration
    g.update_wave_progression()

    assert em.big_spawned_this_wave is False
    # multiplier should follow the stage-aware slope (default stage None uses global)
    expected = 1.0 + g.wave * g.get_difficulty_multiplier_per_wave()
    assert g.difficulty_multiplier == expected


def test_wave_progression_uses_wave_duration():
    """Ensure the wave increments only after the current wave_duration seconds.

    This guards future tunings that might adjust DEFAULT_WAVE_DURATION.
    """
    pygame.init()
    g = Game(debug=True)
    # no progression if time slightly less
    g.wave = 5
    g.wave_time = g.wave_duration - 0.1
    g.update_wave_progression()
    assert g.wave == 5

    # progression once we hit or exceed the duration
    g.wave_time = g.wave_duration
    g.update_wave_progression()
    assert g.wave == 6
