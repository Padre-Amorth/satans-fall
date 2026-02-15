import pygame

pygame.init()
from src.entities.enemy import Enemy  # noqa: E402
from src.game import Game  # noqa: E402


def test_sprite_enemy_contact_emits_particles():
    g = Game()
    g.select_stage("limbo")
    # Place enemy directly on player to force contact
    e = Enemy(g.player.x, g.player.y, enemy_type="normal")
    g.enemies.add(e)

    # Run collision handling
    g.handle_collisions()

    assert len(e.burn_particles) > 0, "Expected enemy to emit burn particles on contact"
    assert (
        hasattr(g.player, "burn_particles") and len(g.player.burn_particles) > 0
    ), "Expected player to emit burn particles on contact"


def test_dict_enemy_contact_emits_particles():
    g = Game()
    g.select_stage("limbo")
    enemy = {
        "x": g.player.x,
        "y": g.player.y,
        "health": 20,
        "max_health": 20,
        "speed": 60,
        "radius": 12,
        "damage": 5,
        "type": "normal",
    }
    g.enemies = [enemy]

    g.handle_collisions()

    assert (
        "burn_particles" in enemy and len(enemy["burn_particles"]) > 0
    ), "Expected dict enemy to include burn_particles on contact"
    assert (
        hasattr(g.player, "burn_particles") and len(g.player.burn_particles) > 0
    ), "Expected player to emit burn particles on contact"
