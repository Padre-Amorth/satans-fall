import pygame

pygame.init()
pygame.font.init()
from src.entities.enemy import Enemy  # noqa: E402
from src.game import Game  # noqa: E402
from src.projectile import Projectile  # noqa: E402


def test_sprite_enemy_emits_ice_particles_on_hit():
    g = Game()
    g.select_stage("limbo")
    e = Enemy(400, 100, enemy_type="normal")
    g.enemies.add(e)

    # Create a projectile that applies slow (ice)
    proj = Projectile(e.x, e.y, 0.0, 0.0, damage=5, radius=6)
    proj.effect = "slow"
    proj.slow_duration = 120
    proj.slow_factor = 0.5

    g.projectiles = []
    g.projectiles.append(proj)

    # Run collision handling
    g.handle_collisions()

    assert (
        len(e.ice_particles) > 0
    ), "Expected ice_particles to be added to sprite enemy on ice hit"


def test_dict_enemy_emits_ice_particles_on_hit():
    g = Game()
    g.select_stage("limbo")
    from src.entities.enemy import Enemy
    from src.projectile import Projectile

    enemy_obj = Enemy(400, 100, enemy_type="normal", health=20)
    enemy_obj.health = 20
    enemy_obj.max_health = 20
    enemy_obj.speed = 60
    enemy_obj.radius = 12
    enemy_obj.damage = 5
    g.enemies = [enemy_obj]

    proj_obj = Projectile(400, 100, 0.0, 0.0, damage=5, radius=6)
    proj_obj.effect = "slow"
    proj_obj.slow_duration = 120
    proj_obj.slow_factor = 0.5
    g.projectiles = [proj_obj]

    # Run collision handling
    g.handle_collisions()

    assert (
        getattr(enemy_obj, "ice_particles", []) and len(enemy_obj.ice_particles) > 0
    ), "Expected ice_particles list for sprite enemy after collision"
