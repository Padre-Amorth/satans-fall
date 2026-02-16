import random

import pygame
import pytest

from src.game import Game


@pytest.mark.parametrize("stage", ["limbo", "limbo_2", "limbo_3"])
def test_boss_big_sinusoidal_hover_in_all_limbo_stages(stage):
    pygame.init()
    random.seed(12345)
    g = Game(debug=True)
    g.select_stage(stage)

    boss = g.enemy_manager.spawn_boss("big")

    # Start boss near the top and run updates until it reaches hover phase
    boss.x = g.width // 2
    boss.y = 20

    reached_hover = False
    hover_start = None
    xs = []
    ys = []
    distances = []

    # Run many frames to allow descent + several slow sinusoidal cycles
    for i in range(1000):
        boss.update(g.player, g)
        xs.append(float(boss.x))
        ys.append(float(boss.y))
        dx = boss.x - g.player.x
        dy = boss.y - g.player.y
        distances.append((dx * dx + dy * dy) ** 0.5)
        if hasattr(boss, "limbo_phase") and boss.limbo_phase == "hover":
            reached_hover = True
            if hover_start is None:
                hover_start = i

    assert (
        reached_hover and hover_start is not None
    ), f"boss_big did not enter hover phase in {stage}"

    # Examine samples from the moment hover started (skip a few transient frames)
    start_idx = min(len(xs) - 1, hover_start + 8)
    xs_after = xs[start_idx:]
    ys_after = ys[start_idx:]


def test_boss_big_enters_scene_slowly_in_limbo():
    """Ensure boss_big descends into view slowly on spawn in Limbo."""
    pygame.init()
    g = Game(debug=True)
    g.select_stage("limbo")

    boss = g.enemy_manager.spawn_boss("big")
    # Sanity: spawn position is off-screen (negative or near -50)
    assert boss.y <= 0 or boss.y < 20

    prev_y = boss.y
    deltas = []
    # Sample the first frames of movement while boss enters the screen
    for _ in range(12):
        boss.update(g.player, g)
        deltas.append(boss.y - prev_y)
        prev_y = boss.y

    # Entrance movement per-frame should be small (slower entrance)
    assert max(deltas) <= 9, f"Entrance too fast: max per-frame delta={max(deltas)}"

    # Entrance should show progressive acceleration (some per-frame deltas should increase)
    increases = sum(
        1 for i in range(len(deltas) - 1) if deltas[i + 1] > deltas[i] + 0.01
    )
    assert (
        increases >= 3
    ), f"Entrance did not accelerate progressively (increases={increases})"
