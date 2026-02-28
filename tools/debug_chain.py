import pygame

from src.entities.enemy import Enemy
from src.game import Game
from src.projectile import Projectile
from src.utils.spatial_grid import SpatialGrid

pygame.init()

g = Game()

# enemies
try:
    g.enemies.empty()
    g.enemies.add(Enemy(400, 100, enemy_type="normal", health=20))
    g.enemies.add(Enemy(420, 100, enemy_type="normal", health=20))
except Exception:
    g.enemies = [
        Enemy(400, 100, enemy_type="normal", health=20),
        Enemy(420, 100, enemy_type="normal", health=20),
    ]

g.spatial_grid = SpatialGrid(cell_size=120, width=g.width, height=g.height)
g.spatial_grid.build(g._enemies_iter())

proj = Projectile(400, 100, 0.0, 0.0, damage=5, radius=6, appearance="storm_statue")
proj.source = "statue"
proj.tower_type = "storm"
proj.chain_targets = 2

try:
    g.projectiles.add(proj)
except Exception:
    g.projectiles = [proj]

# run collision
print("before ftexts", g.floating_texts)
g.handle_collisions()
print(
    "after e1 health",
    (
        g.enemies.sprites()[0].health
        if hasattr(g.enemies, "sprites")
        else g.enemies[0].health
    ),
)
print("ftexts:")
for ft in g.floating_texts:
    print("text", getattr(ft, "text", None), "color", getattr(ft, "color", None))
