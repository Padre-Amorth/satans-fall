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
    enemy = {
        "x": 400,
        "y": 100,
        "health": 20,
        "max_health": 20,
        "speed": 60,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    g.enemies = [enemy]

    proj = {
        "x": 400,
        "y": 100,
        "vel_x": 0.0,
        "vel_y": 0.0,
        "damage": 5,
        "radius": 6,
        "effect": "slow",
        "slow_duration": 120,
        "slow_factor": 0.5,
    }
    g.projectiles = []
    g.projectiles.append(proj)

    # Run collision handling
    g.handle_collisions()

    assert (
        "ice_particles" in enemy and len(enemy["ice_particles"]) > 0
    ), "Expected ice_particles list for dict-based enemy after collision"
