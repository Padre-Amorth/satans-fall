import pygame

from src.game import Game


def test_inquisitor_roams_in_top_half_and_speed():
    pygame.init()
    g = Game(debug=True)
    boss = g.enemy_manager.spawn_boss("inquisitor")

    # speed was slightly increased (spawned value)
    # Verify slight speed increase applied
    assert getattr(boss, "speed", 0) >= 34
    # Initial shoot cooldown should be in the reduced-rate range
    assert getattr(boss, "shoot_cooldown", 0) >= 100

    # Place boss near top; run many update ticks to let it pick roam targets
    boss.x = g.width // 2
    boss.y = 40

    xs = set()
    ys = set()
    for _ in range(300):
        boss.update(g.player, g)
        xs.add(int(boss.x))
        ys.add(int(boss.y))
        # Ensure boss never crosses halfway down the playfield
        assert boss.y <= g.height / 2
        assert boss.y >= 30

    # Boss should have moved horizontally/selected multiple targets
    assert len(xs) > 5
    # Boss should remain in the top half (no crossing)
    assert max(ys) <= g.height / 2
    # Roam target should exist and be within the allowed region
    assert hasattr(boss, "roam_target")
    rx, ry = boss.roam_target
    # Roam target should be inside arena walls and within top-half
    assert g.clamp_to_walls(0) <= rx <= g.clamp_to_walls(g.width)
    assert 30 <= ry <= g.height / 2 - 40