import pygame

from src.entities.enemy import Enemy
from src.game import Game
from src.projectile import Projectile

pygame.init()

g = Game()

g.player_weapons = ["DemonStrike"]

g.player.x = 50
g.player.y = 100

enemy = Enemy(50, 160, health=100)
g.enemies = [enemy]

# Create DemonStrike projectile
ds = Projectile(
    g.player.x, g.player.y, 0, 800, damage=10, radius=6, weapon_type="DemonStrike"
)
ds.pierce_all = True
ds.effect = "slow"
ds.slow_duration = 120

g.projectiles = [ds] if not hasattr(g.projectiles, "add") else g.projectiles
if not hasattr(g.projectiles, "add"):
    g.projectiles.append(ds)

print("initial enemy health:", enemy.health)
for i in range(8):
    for p in list(g.projectiles):
        try:
            p.update()
        except Exception:
            pass
    print(
        f"Frame {i} BEFORE: enemy.health={enemy.health}, ds._hit_ids={getattr(ds, '_hit_ids', None)}"
    )
    g.handle_collisions()
    print(
        f"Frame {i} AFTER:  enemy.health={enemy.health}, ds._hit_ids={getattr(ds, '_hit_ids', None)}"
    )

print("final enemy health:", enemy.health)
