import pygame

from src.game import Game


def test_limbo_final_boss_is_triple_size():
    pygame.init()
    g = Game(debug=True)
    em = g.enemy_manager
    boss = em.spawn_boss("limbo")
    # original default width before triple = 40 (30+10)
    assert boss.width == 120
    assert boss.height == 120
    # report pixel dimensions for user information
    print(f"Limbo final boss dimensions: {boss.width}x{boss.height} pixels")
