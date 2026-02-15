import pygame

from src.game import Game
from src.projectile import Projectile


def test_spear_hits_boss_only_once():
    pygame.init()
    g = Game(debug=True)

    # spawn a medium boss and place it in front of player
    boss = g.enemy_manager.spawn_boss("mid")
    boss.x = g.player.x + 50
    boss.y = g.player.y
    try:
        boss.rect.center = (boss.x, boss.y)
    except Exception:
        pass

    # create a spear projectile aimed to the right
    spear = Projectile(
        g.player.x, g.player.y, 800, 0, damage=30, radius=6, weapon_type="spear"
    )
    spear.pierce_all = True

    # Put projectile into game projectiles (support both Group and list)
    try:
        g.projectiles.add(spear)
    except Exception:
        g.projectiles = [spear]

    # Simulate a few frames where collision might be detected multiple times
    for _ in range(6):
        # move projectile forward
        spear.update()
        try:
            spear.rect.center = (spear.x, spear.y)
        except Exception:
            pass
        g.handle_collisions()

    # Boss should have been damaged exactly once (no multi-hit from spear)
    assert boss.health == boss.max_health - spear.damage
