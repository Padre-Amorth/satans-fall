import pygame

from src.balance import BASE_SPAWN_RATE, SPAWN_MIN_RATE, SPAWN_RAMP_SLOPE_POST
from src.game_state import GameStateManager
from src.game import Game


def test_spawn_rate_reaches_min_around_wave_10():
    """Spawn rate should hit SPAWN_MIN_RATE at wave ~10 with the new slope"""
    pygame.init()
    g = Game(debug=True)
    gsm = g.game_state

    # Advance waves until spawn rate == SPAWN_MIN_RATE and record the wave
    reached_at = None
    # Start from wave 0 and call advance_wave repeatedly
    gsm.wave = 0
    for _ in range(1, 30):
        gsm.advance_wave()
        rate = g.enemy_manager.enemy_spawn_rate
        if rate == SPAWN_MIN_RATE and reached_at is None:
            reached_at = gsm.wave
            break

    # With SPAWN_RAMP_SLOPE_POST ~= 4.2 and BASE_SPAWN_RATE 72, we expect min reached around wave 10
    assert reached_at is not None, "spawn rate never reached SPAWN_MIN_RATE"
    assert 9 <= reached_at <= 11, f"expected spawn_min_rate around wave 10, reached at wave {reached_at} (slope_post={SPAWN_RAMP_SLOPE_POST})"