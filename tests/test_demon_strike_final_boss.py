import pygame

from src.game import Game
from src.projectile import Projectile


def test_demon_strike_hits_final_boss_only_once():
    pygame.init()
    g = Game(debug=True)

    # Ensure no regular enemies will intercept the projectile
    g.enemies = []

    # spawn a final boss and place it under the player
    boss = g.enemy_manager.spawn_boss("final")
    boss.x = g.player.x
    boss.y = g.player.y + 80
    try:
        boss.rect.center = (boss.x, boss.y)
    except Exception:
        pass

    # create a DemonStrike projectile aimed downward (vertical)
    ds = Projectile(
        g.player.x, g.player.y, 0, 800, damage=30, radius=6, weapon_type="DemonStrike"
    )
    ds.pierce_all = True

    try:
        g.projectiles.add(ds)
    except Exception:
        g.projectiles = [ds]

    # Simulate frames where projectile may overlap boss multiple times
    for _ in range(12):
        ds.update()
        try:
            ds.rect.center = (ds.x, ds.y)
        except Exception:
            pass
        g.handle_collisions()

    # Final boss should have been damaged exactly once by this projectile
    assert boss.health == boss.max_health - ds.damage
