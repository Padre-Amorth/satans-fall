import pygame

from src.entities.enemy import Enemy
from src.game import Game


def test_no_floating_damage_text_on_sprite_contact():
    pygame.init()
    g = Game()
    g.select_stage("limbo")

    e = Enemy(g.player.x, g.player.y, enemy_type="normal")
    try:
        g.enemies.empty()
        g.enemies.add(e)
    except Exception:
        g.enemies = [e]

    # Ensure no floating texts before contact
    assert getattr(g, "floating_texts", []) == []

    g.handle_collisions()

    # Damage numbers must NOT be shown for contact damage with Satan
    assert getattr(g, "floating_texts", []) == []


def test_no_floating_damage_text_on_dict_contact():
    pygame.init()
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

    assert getattr(g, "floating_texts", []) == []

    g.handle_collisions()

    assert getattr(g, "floating_texts", []) == []
