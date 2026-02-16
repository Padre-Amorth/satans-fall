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
