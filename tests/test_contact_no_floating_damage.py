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


# additional regression: contact damage should tick once every two seconds
# and not apply continuously


def test_contact_damage_tick_every_two_seconds():
    """Enemies in continuous contact take a lump every 2 seconds."""
    pygame.init()
    g = Game()
    g.reset_game()
    g.select_stage("limbo")

    e = Enemy(g.player.x, g.player.y, enemy_type="normal")
    try:
        g.enemies.empty()
        g.enemies.add(e)
    except Exception:
        g.enemies = [e]

    hp_before = e.health
    # Contact damage is applied as a lump every ~2 seconds (fps*2 frames).
    # Verify that damage is NOT applied every frame (i.e. the first few
    # frames of contact should not reduce enemy health).
    for _ in range(10):
        g.handle_collisions()
    assert e.health == hp_before, "Contact damage should not apply immediately"

    # Run enough frames for the timer to expire and verify a single 4 HP
    # tick occurs within the expected window.
    frames = int(g.fps * 2)
    for _ in range(frames + 5):
        g.handle_collisions()
    # At least one tick of 4 HP should have been applied
    damage_taken = hp_before - e.health
    assert damage_taken >= 4, f"Expected at least 4 damage, got {damage_taken}"
    assert damage_taken % 4 == 0, f"Damage should be in multiples of 4, got {damage_taken}"
