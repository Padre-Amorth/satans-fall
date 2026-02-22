import random

import pygame

from src.game import Game

pygame.init()

g = Game(debug=True)


class DummyEnemy(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.x = 100
        self.y = 100
        self.health = 100
        self.max_health = 100
        self.enemy_type = "normal"
        self.rect = pygame.Rect(self.x - 10, self.y - 10, 20, 20)


class DummyProj(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.x = 100
        self.y = 100
        self.radius = 5
        self.damage = 10
        self.is_enemy_projectile = False
        self.source = None
        self.rect = pygame.Rect(self.x - 2, self.y - 2, 4, 4)


enemy = DummyEnemy()
proj = DummyProj()

g.enemies = pygame.sprite.Group()
g.enemies.add(enemy)

g.projectiles = pygame.sprite.Group()
g.projectiles.add(proj)

# set stats and force crit
g.permanent_stats["adrenaline"] = 1
g.permanent_stats["blasphemy_6"] = 0
random.random = lambda: 0.0

print("candidates", g.collision_system._get_hit_enemies_for_projectile(proj))
print("enemy pos", g._enemy_pos(enemy), "proj pos", proj.x, proj.y)
print(
    "enemy rad",
    g._enemy_radius(enemy),
    "proj rad",
    g.collision_system._projectile_radius(proj),
)

print(
    "dmg helper result",
    g.collision_system._player_damage_vs_burning(proj, enemy, proj.damage),
)
# run normal collision first
print("pre-collision health", enemy.health, "floating", len(g.floating_texts))
g.collision_system.handle_collisions()
print("post-collision health", enemy.health, "floating", len(g.floating_texts))

# reset for plain-list branch
enemy.health = 100
g.floating_texts.clear()
print("\n--- plain-list branch ---")
# monkeypatch detection to return empty
original = g.collision_system._get_hit_enemies_for_projectile
g.collision_system._get_hit_enemies_for_projectile = lambda proj: []
print(
    "candidates after override",
    g.collision_system._get_hit_enemies_for_projectile(proj),
)
print("pre2 health", enemy.health, "floating", len(g.floating_texts))
g.collision_system.handle_collisions()
print("post2 health", enemy.health, "floating", len(g.floating_texts))
for ft in g.floating_texts:
    print("ft text", ft.text, "color", ft.color)
# restore
g.collision_system._get_hit_enemies_for_projectile = original
for ft in g.floating_texts:
    print("ft text", ft.text, "color", ft.color)
