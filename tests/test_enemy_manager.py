import pygame

from src.game import Game
from src.entities.enemy import Enemy


def test_spawn_and_recycle():
    pygame.init()
    g = Game(debug=True)
    em = g.enemy_manager
    assert em is not None

    # Spawn an enemy via manager
    e = em.spawn(100, 100, "weak", health=10, speed=50)

    # It should be in game's enemies container
    found = False
    try:
        for en in g.enemies:
            if en is e:
                found = True
                break
    except Exception:
        if e in g.enemies:
            found = True
    assert found

    # Recycle the enemy
    em.recycle(e)

    # After recycle, it shouldn't be active and should be in pool
    assert e not in em.active
    assert e in em.pool


def test_spawn_via_game_spawn_enemy():
    pygame.init()
    g = Game(debug=True)
    # Call the game's spawn helper which should use EnemyManager
    g.spawn_enemy()

    # Expect at least one enemy in container
    assert len(list(g.enemies)) >= 1
    # Manager active list should reflect it
    if g.enemy_manager is not None:
        assert len(g.enemy_manager.active) >= 1


def test_non_boss_spawn_speed_matches_spawn_value():
    """Non-boss spawns (weak, normal, strong, angel, giant) should use the spawn `speed` directly (no global modifier)."""
    from unittest.mock import patch

    pygame.init()
    g = Game(debug=True)

    # 1) Force the 'normal' branch
    with patch('random.random', return_value=0.1):
        g.spawn_enemy()
    spawned = next((en for en in g.enemies if getattr(en, 'enemy_type', None) == 'normal'), None)
    assert spawned is not None
    # spawn speed for normal is currently 60 in spawn logic
    assert abs(spawned.speed - 60.0) < 0.001

    # 2) Spawn reinforcements covering weak/strong/angel
    # Clear game's enemy container in a safe, container‑agnostic way
    try:
        for _e in list(g.enemies):
            try:
                g.enemies.remove(_e)
            except Exception:
                pass
    except Exception:
        try:
            g.enemies = []
        except Exception:
            pass

    g.spawn_reinforcements(x=200, y=80, count=6)
    # Ensure at least one non-boss enemy spawned and all non-boss enemies use spawn speed
    non_bosses = [en for en in g.enemies if getattr(en, 'enemy_type', '').startswith(('weak','normal','strong','angel','giant'))]
    assert len(non_bosses) >= 1
    for en in non_bosses:
        assert abs(en.speed - 60.0) < 0.001

    # 3) Spawn a giant via manager/fallback
    # Clear container safely
    try:
        for _e in list(g.enemies):
            try:
                g.enemies.remove(_e)
            except Exception:
                pass
    except Exception:
        try:
            g.enemies = []
        except Exception:
            pass

    g.spawn_giant_enemy()
    giant = next((en for en in g.enemies if getattr(en, 'enemy_type', None) == 'giant'), None)
    assert giant is not None
    # giant spawn speed aligned to non-boss spawn speed (60)
    assert abs(giant.speed - 60.0) < 0.001
