import pygame

from src.game import Game


def test_boss_big_roams_in_top_half_and_does_not_chase_player():
    pygame.init()
    g = Game(debug=True)
    g.select_stage("limbo")

    boss = g.enemy_manager.spawn_boss("big")

    # Place boss near top; run many update ticks to let it pick roam targets
    boss.x = g.width // 2
    boss.y = 40

    xs = set()
    ys = set()
    distances = []
    for _ in range(300):
        boss.update(g.player, g)
        xs.add(int(boss.x))
        ys.add(int(boss.y))
        # Ensure boss never crosses halfway down the playfield
        assert boss.y <= g.height / 2
        assert boss.y >= 20
        # track distance to player (should not steadily decrease toward player)
        dx = boss.x - g.player.x
        dy = boss.y - g.player.y
        distances.append((dx * dx + dy * dy) ** 0.5)

    # Boss should have moved horizontally/selected multiple targets
    assert len(xs) > 5
    # Boss should remain in the upper half (no crossing)
    assert max(ys) <= g.height / 2
    # Distance to player should not monotonically decrease; ensure average distance stays large
    assert sum(distances) / len(distances) > (g.height / 3)
    # Roam target should exist and be within the allowed region
    assert hasattr(boss, "roam_target")
    rx, ry = boss.roam_target
    assert g.clamp_to_walls(0) <= rx <= g.clamp_to_walls(g.width)
    assert 20 <= ry <= g.height / 2 - 20
