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
    enemy["burn_timer"] = 60
    enemy["burn_damage_per_second"] = 2
    g.enemies = [enemy]

    # Draw should not crash
    g.draw()
