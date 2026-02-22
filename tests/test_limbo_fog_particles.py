import pygame

from src.game import Game


def test_limbo_no_fog_particles_anymore():
    """Limbo stages should not emit or track any fog particles.
    The entire system has been removed, so the UI should never create the
    `_limbo_fog_particles` attribute (or if it exists, it should remain empty).
    """
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"
    g.generate_walls()

    ui = g.ui
    screen = pygame.Surface((g.width, g.height))
    ui.screen = screen

    # call several times to simulate multiple frames
    for _ in range(20):
        ui.draw_fog()

    # the attribute should either be missing or an empty list
    parts = getattr(ui, "_limbo_fog_particles", None)
    assert parts in (None, []), "Limbo fog particles should no longer be used"

    # ensure no errors occurred and screen still valid
    assert isinstance(screen, pygame.Surface)
