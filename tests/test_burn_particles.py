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
    g.enemies = [enemy]

    # Call draw which also spawns/updates dict-based particles
    g.draw()

    assert (
        "burn_particles" in enemy and len(enemy["burn_particles"]) > 0
    ), "Expected burn_particles list for dict-based enemy after draw"
