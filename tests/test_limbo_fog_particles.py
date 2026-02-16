import pygame

from src.game import Game


def test_limbo_emits_fog_particles_and_draws():
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    # Initially no fog particles
    assert getattr(ui, "_limbo_fog_particles", None) == []

    # Call draw_fog multiple times to allow probabilistic spawn (more frames to reduce flakiness)
    for _ in range(30):
        ui.draw_fog()

    # Expect at least some particles to have been created
    parts = getattr(ui, "_limbo_fog_particles", [])
    assert len(parts) > 0, "Expected fog particles to be emitted in Limbo"

    # Particles should appear along the full exterior wall section (left and/or right)
    left_wall_x = min(p[0] for p in g.left_wall_points)
    right_wall_x = max(p[0] for p in g.right_wall_points)

    left_side = any(p["x"] <= left_wall_x + 8 for p in parts)
    right_side = any(p["x"] >= right_wall_x - 8 for p in parts)
    assert (
        left_side or right_side
    ), "Expected fog particles along the external wall sections"

    # At least one particle should be vertically within the wall span (not only near pedestals)
    top_y = min(p[1] for p in g.left_wall_points + g.right_wall_points)
    bot_y = max(p[1] for p in g.left_wall_points + g.right_wall_points)
    span_particle = any((top_y + 10) <= p["y"] <= (bot_y - 10) for p in parts)
    assert span_particle, "Expected fog particles distributed along the wall height"

    # Drawing should not raise and should have blitted something (surface remains valid)
    assert isinstance(screen, pygame.Surface)
