import pygame

from src.game import Game


def test_limbol_statues_drawn():
    """Limbo and limbo_final stages should show statues even without pedestals.

    The test ensures that the pixel at the old pedestal head position now
    contains the statue colour rather than remaining untouched.
    """
    pygame.init()
    g = Game()

    # limbo: statue should be present (non-black)
    g.select_stage("limbo")
    g.screen.fill((0, 0, 0))
    g.ui.draw_pedestals()
    from src import game_constants

    sample_x = 370
    sample_y = 620 - 10 - 70 + game_constants.STATUE_ASSET_VERTICAL_OFFSET
    pix = tuple(g.screen.get_at((sample_x, sample_y))[:3])
    assert pix != (0, 0, 0), f"Expected nonblack pixel in limbo, got {pix}"

    # limbo_final: no static statues, expect black
    g.select_stage("limbo_final")
    g.screen.fill((0, 0, 0))
    g.ui.draw_pedestals()
    pix2 = tuple(g.screen.get_at((sample_x, sample_y))[:3])
    assert pix2 == (0, 0, 0), f"Expected black pixel in limbo_final, got {pix2}"
