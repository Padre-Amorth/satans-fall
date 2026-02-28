import pygame

from src.game import Game
from src.game_constants import (
    LIMBO_FINAL_ACCEL_START_TIME,
    LIMBO_FINAL_HALT_BEFORE_BOSS,
)


def test_limbo_final_spawn_rate_changes_after_30_seconds():
    pygame.init()
    g = Game(debug=True)
    g.select_stage("limbo_final")
    # ramp slopes should be steeper in limbo_final
    from src.balance import SPAWN_RAMP_SLOPE_POST, SPAWN_RAMP_SLOPE_PRE

    assert g.spawn_ramp_slope_pre == SPAWN_RAMP_SLOPE_PRE * 2
    assert g.spawn_ramp_slope_post == SPAWN_RAMP_SLOPE_POST * 2
    ss = g.spawn_system

    # record timer before threshold
    g.wave_time = LIMBO_FINAL_ACCEL_START_TIME - 1
    ss.update_enemy_spawning()
    before = getattr(g.enemy_manager or g, "enemy_spawn_timer")

    # after threshold should be lower
    g.wave_time = LIMBO_FINAL_ACCEL_START_TIME + 1
    ss.update_enemy_spawning()
    after = getattr(g.enemy_manager or g, "enemy_spawn_timer")

    assert after < before


def test_limbo_final_halts_spawning_before_boss():
    pygame.init()
    g = Game(debug=True)
    g.select_stage("limbo_final")
    ss = g.spawn_system

    spawned = 0
    original_spawn = ss.spawn_enemy

    def count_spawn():
        nonlocal spawned
        spawned += 1
        original_spawn()

    ss.spawn_enemy = count_spawn

    # just before halt window
    g.wave_time = 180 - LIMBO_FINAL_HALT_BEFORE_BOSS - 0.5
    for _ in range(5):
        ss.update_enemy_spawning()
    assert spawned > 0

    spawned = 0
    g.wave_time = 180 - LIMBO_FINAL_HALT_BEFORE_BOSS + 0.5
    for _ in range(5):
        ss.update_enemy_spawning()
    assert spawned == 0


def test_limbo_final_halts_by_total_time():
    pygame.init()
    g = Game(debug=True)
    g.select_stage("limbo_final")
    ss = g.spawn_system
    # wave_time small but elapsed time past threshold
    g.wave_time = 1.0
    g.time_elapsed = 180 - LIMBO_FINAL_HALT_BEFORE_BOSS + 0.1
    spawned = 0
    orig = ss.spawn_enemy

    def count():
        nonlocal spawned
        spawned += 1
        orig()

    ss.spawn_enemy = count
    for _ in range(5):
        ss.update_enemy_spawning()
    assert spawned == 0


def test_limbo_final_boss_sprite_resized_on_spawn():
    pygame.init()
    g = Game(debug=True)
    g.select_stage("limbo_final")
    # simulate time so boss spawns via normal event
    g.time_elapsed = 180
    g.update_prologo_events()
    bosses = [b for b in g.bosses if getattr(b, "enemy_type", "") == "boss_limbo"]
    assert bosses, "boss should have spawned"
    boss = bosses[0]
    assert boss.width == 120 and boss.height == 120


def test_limbo_boss_hitbox_is_smaller_than_sprite():
    """Verify the collision rect is significantly smaller than the image."""
    pygame.init()
    g = Game(debug=True)
    g.select_stage("limbo_final")
    boss = g.enemy_manager.spawn_boss("limbo")
    # rect inflated 40% smaller on each dimension
    assert boss.rect.width < boss.width
    assert boss.rect.height < boss.height
    # make sure shrink is substantial (at least 20 pixels each direction)
    assert boss.width - boss.rect.width >= 20
    assert boss.height - boss.rect.height >= 20


def test_no_wave_boss_after_limbo_spawn():
    """Once the Limbo Final boss has appeared, update_wave_boss should be a no-op.

    This prevents an Inquisitor or other wave boss from showing up while the
    final encounter is in progress.
    """
    pygame.init()
    g = Game(debug=True)
    g.select_stage("limbo_final")
    em = g.enemy_manager

    # pretend the boss has already spawned
    em.limbo_final_boss_spawned = True
    g.wave_time = 38
    em.wave_boss_spawned = False

    before = len(g.bosses)
    em.update_wave_boss(g.wave_time)
    assert len(g.bosses) == before, "No new boss should be added after limbo boss"


def test_no_wave_progression_after_limbo_spawn():
    """Wave counter should remain frozen once the limbo boss arrives."""
    pygame.init()
    g = Game(debug=True)
    g.select_stage("limbo_final")
    ss = g.spawn_system

    g.wave = 2
    g.wave_time = g.wave_duration + 0.1
    g.enemy_manager.limbo_final_boss_spawned = True

    ss.update_wave_progression()
    assert g.wave == 2, "Wave number should not increment after limbo boss"
    assert g.wave_time > 0, "Wave time should not be reset after limbo boss"
