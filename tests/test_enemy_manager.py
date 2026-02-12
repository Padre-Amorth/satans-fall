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


def test_normal_spawn_effective_speed():
    """Normal spawn should have effective speed 60 after global ×0.8 tuning."""
    import random
    from unittest.mock import patch

    pygame.init()
    g = Game(debug=True)

    # Force the 'normal' branch by patching random.random to return < 0.3
    with patch('random.random', return_value=0.1):
        g.spawn_enemy()

    # Find a spawned normal enemy
    spawned = None
    try:
        for en in g.enemies:
            if getattr(en, 'enemy_type', None) == 'normal':
                spawned = en
                break
    except Exception:
        for en in list(g.enemies):
            if getattr(en, 'enemy_type', None) == 'normal':
                spawned = en
                break

    assert spawned is not None
    # Effective speed should be 75 * 0.8 = 60
    assert abs(spawned.speed - 60) < 0.0001
