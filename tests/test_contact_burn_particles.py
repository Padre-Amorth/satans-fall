import pygame

pygame.init()
from src.entities.enemy import Enemy  # noqa: E402
from src.game import Game  # noqa: E402


def test_sprite_enemy_contact_no_particles():
    g = Game()
    g.select_stage("limbo")
    # Place enemy directly on player to force contact
    e = Enemy(g.player.x, g.player.y, enemy_type="normal")
    g.enemies.add(e)

    # Run collision handling
    g.handle_collisions()

    # No burn particles should be created on simple contact
    assert not getattr(
        e, "burn_particles", []
    ), "Enemy should not emit burn particles on contact"
    assert not getattr(
        g.player, "burn_particles", []
    ), "Player should not emit burn particles on contact"


def test_dict_enemy_contact_no_particles():
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

    assert not getattr(
        enemy_obj, "burn_particles", []
    ), "Dictionary-style enemy should not gain burn_particles on contact"
    assert not getattr(
        g.player, "burn_particles", []
    ), "Player should not emit burn particles on contact"
