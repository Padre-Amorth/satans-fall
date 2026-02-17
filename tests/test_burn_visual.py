import pygame

pygame.init()
pygame.font.init()
from src.entities.enemy import Enemy  # noqa: E402
from src.game import Game  # noqa: E402


def test_enemy_sprite_draws_burn_effect():
    g = Game()
    g.select_stage("limbo")
    # Create enemy sprite and set burn
    e = Enemy(400, 100, enemy_type="normal")
    e.burn_timer = 60
    e.burn_damage_per_second = 2
    g.enemies.add(e)

    # Draw should not crash
    g.draw()


def test_dict_enemy_draws_burn_effect():
    g = Game()
    g.select_stage("limbo")
    from src.entities.enemy import Enemy

    enemy_obj = Enemy(400, 100, enemy_type="normal", health=20)
    enemy_obj.health = 20
    enemy_obj.max_health = 20
    enemy_obj.speed = 60
    enemy_obj.radius = 12
    enemy_obj.damage = 5
    enemy_obj.burn_timer = 60
    enemy_obj.burn_damage_per_second = 2
    g.enemies = [enemy_obj]

    # Draw should not crash
    g.draw()
