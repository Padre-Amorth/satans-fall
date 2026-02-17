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
    from src.entities.enemy import Enemy

    enemy_obj = Enemy(g.player.x, g.player.y, enemy_type="normal", health=20)
    enemy_obj.health = 20
    enemy_obj.max_health = 20
    enemy_obj.speed = 60
    enemy_obj.radius = 12
    enemy_obj.damage = 5
    g.enemies = [enemy_obj]

    g.handle_collisions()

    assert (
        getattr(enemy_obj, "burn_particles", []) and len(enemy_obj.burn_particles) > 0
    ), "Expected enemy to include burn_particles on contact"
    assert (
        hasattr(g.player, "burn_particles") and len(g.player.burn_particles) > 0
    ), "Expected player to emit burn particles on contact"
