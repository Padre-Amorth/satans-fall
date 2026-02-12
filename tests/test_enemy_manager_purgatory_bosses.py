import pygame

from src.game import Game


def test_purgatory_wave_boss_alternates():
    pygame.init()
    g = Game(debug=True)
    g.select_stage("purgatory")
    em = g.enemy_manager

    # Wave 1 (odd) -> medium boss
    g.wave = 1
    em.wave_boss_spawned = False
    # Simulate wave-time reaching boss spawn
    em.update_wave_boss(28)
    bosses = [b for b in g.bosses if getattr(b, "enemy_type", "").startswith("boss_")]
    assert any(getattr(b, "enemy_type", "") == "boss_medium" for b in bosses)

    # Clear bosses and test even wave -> inquisitor
    try:
        g.bosses.empty()
    except Exception:
        g.bosses = []
    em.wave_boss_spawned = False
    g.wave = 2
    em.update_wave_boss(28)
    bosses = [b for b in g.bosses if getattr(b, "enemy_type", "").startswith("boss_")]
    assert any(getattr(b, "enemy_type", "") == "boss_inquisitor" for b in bosses)
