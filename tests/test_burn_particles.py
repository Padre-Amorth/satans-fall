import pygame

pygame.init()
pygame.font.init()
from src.entities.enemy import Enemy  # noqa: E402
from src.game import Game  # noqa: E402


def test_sprite_enemy_emits_particles():
    g = Game()
    g.select_stage("limbo")
    e = Enemy(400, 100, enemy_type="normal")
    # Apply burn and step a few frames
    e.burn_timer = 60
    e.burn_damage_per_second = 1
    g.enemies.add(e)

    # Run several updates to allow emission
    for _ in range(5):
        e.update(g.player, g)

    assert (
        len(e.burn_particles) > 0
    ), "Expected burn particles to be emitted for sprite enemy"

    # Wait until burn_timer expires and then allow particles to die out
    while getattr(e, "burn_timer", 0) > 0:
        e.update(g.player, g)
    # Run extra frames so remaining particles can decay
    for _ in range(80):
        e.update(g.player, g)
    assert (
        len(e.burn_particles) == 0
    ), f"Expected particles to die out after burn, remaining: {len(e.burn_particles)}"


def test_dict_enemy_emits_particles_on_draw():
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
    g.enemies = [enemy_obj]

    # Enemy instances spawn burn particles during their update()
    for _ in range(4):
        enemy_obj.update(g.player, g)

    assert (
        getattr(enemy_obj, "burn_particles", []) and len(enemy_obj.burn_particles) > 0
    ), "Expected burn_particles list for enemy after update()"
