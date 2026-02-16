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

    assert getattr(g, "floating_texts", []) == []

    g.handle_collisions()

    assert getattr(g, "floating_texts", []) == []
