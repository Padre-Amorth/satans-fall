import random

from src.game import Game
from src.ui import PygameUIManager


def test_limbo2_fog_spawns_mixed_colors():
    random.seed(1)
    g = Game(debug=True)
    ui = PygameUIManager(g)

    # Provide simple wall points so spawning can occur
    g.left_wall_points = [(100, 400), (100, 480)]
    g.right_wall_points = [(700, 400), (700, 480)]
    g.selected_stage = "limbo_2"

    # Ensure no particles initially
    ui._limbo_fog_particles.clear()

    # Call spawn repeatedly to accumulate particles deterministically
    for _ in range(8):
        ui._spawn_limbo_fog_particles()

    assert ui._limbo_fog_particles, "Expected fog particles to be spawned in limbo_2"

    types = {p.get("color_type") for p in ui._limbo_fog_particles}
    # Expect both 'yellow' and 'white' appear among spawned particles
    assert "yellow" in types and "white" in types

    # Alpha values should be lower (more transparent) for limbo_2 spawns
    alphas = [p.get("alpha", 0) for p in ui._limbo_fog_particles]
    assert alphas and max(alphas) <= 30 and min(alphas) >= 5

    # Also verify drawing doesn't crash and uses the surface
    ui._update_and_draw_limbo_fog_particles()


def test_limbo3_fog_spawns_yellow_and_red():
    random.seed(2)
    g = Game(debug=True)
    ui = PygameUIManager(g)

    # Provide simple wall points so spawning can occur
    g.left_wall_points = [(100, 400), (100, 480)]
    g.right_wall_points = [(700, 400), (700, 480)]
    g.selected_stage = "limbo_3"

    ui._limbo_fog_particles.clear()
    for _ in range(8):
        ui._spawn_limbo_fog_particles()

    assert ui._limbo_fog_particles, "Expected fog particles to be spawned in limbo_3"

    types = {p.get("color_type") for p in ui._limbo_fog_particles}
    # Expect both 'yellow' and 'red' appear among spawned particles
    assert "yellow" in types and "red" in types

    alphas = [p.get("alpha", 0) for p in ui._limbo_fog_particles]
    assert alphas and max(alphas) <= 30 and min(alphas) >= 5

    ui._update_and_draw_limbo_fog_particles()
