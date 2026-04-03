import pygame

from src.entities.enemy import Enemy
from src.game import Game
from src.projectile import Projectile


def test_storm_projectile_removed_on_contact_object():
    pygame.init()
    g = Game()

    e = Enemy(400, 100, enemy_type="normal", health=20)
    try:
        g.enemies.empty()
        g.enemies.add(e)
    except Exception:
        g.enemies = [e]

    proj = Projectile(400, 100, 0.0, 0.0, damage=5, radius=6, appearance="storm_statue")
    proj.source = "statue"

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles = [proj]

    g.handle_collisions()

    # Projectile must be removed/killed after contact
    try:
        assert proj not in list(g.projectiles)
    except Exception:
        assert proj not in g.projectiles


def test_storm_projectile_removed_on_contact_dict():
    pygame.init()
    g = Game()

    # Use object-style enemy (converted from dict)
    e = Enemy(400, 100, enemy_type="normal", health=20)
    try:
        g.enemies.empty()
        g.enemies.add(e)
    except Exception:
        g.enemies = [e]

    proj = Projectile(400, 100, 0.0, 0.0, damage=5, radius=6, appearance="storm_statue")
    proj.source = "statue"

    try:
        g.projectiles.add(proj)
    except Exception:
        g.projectiles = [proj]

    g.handle_collisions()

    # Projectile must be removed/killed after contact
    try:
        assert proj not in list(g.projectiles)
    except Exception:
        assert proj not in g.projectiles
