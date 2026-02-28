import pygame

from src.balance import SPAWN_MIN_RATE, SPAWN_RAMP_SLOPE_POST
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
    assert (
        9 <= reached_at <= 11
    ), f"expected spawn_min_rate around wave 10, reached at wave {reached_at} (slope_post={SPAWN_RAMP_SLOPE_POST})"

    # multiplier sanity check – recalc via update_wave_progression (wave changed by advance_wave)
    gsm.update_wave_progression()
    expected = 1.0 + reached_at * g.get_difficulty_multiplier_per_wave()
    assert abs(gsm.difficulty_multiplier - expected) < 1e-6


def test_limbolike_spawn_penalty_counts():
    """Limbo stages should spawn about two fewer enemies per 10 seconds.

    This test exercises the frame-delay penalty indirectly by converting
    spawn_rate to enemies per 10s and checking it falls in the expected
    decreased ranges described by the design notes.
    """
    pygame.init()
    g = Game(debug=True)
    g.reset_game()
    g.select_stage("limbo")

    # wave 0: expect 6-8 enemies per 10s
    rate0 = g.enemy_manager.enemy_spawn_rate
    per10 = 600 / rate0
    assert 6 <= per10 <= 8, f"wave0 limbo spawn {per10:.1f} per 10s"

    # advance to a mid-wave (e.g. wave 5) and recompute
    for _ in range(5):
        g.game_state.advance_wave()
    rate_mid = g.enemy_manager.enemy_spawn_rate
    per10_mid = 600 / rate_mid
    # mid waves should still be roughly in the 10–18 window after penalty
    assert 10 <= per10_mid <= 18, f"mid wave limbo spawn {per10_mid:.1f} per 10s"

    # ensure penalty applied relative to non-limbo base: compare with a fresh
    # non-limbo game at same wave
    g2 = Game(debug=True)
    g2.reset_game()
    g2.select_stage("purgatory")
    for _ in range(5):
        g2.game_state.advance_wave()
    assert g2.enemy_manager.enemy_spawn_rate < rate_mid
