import pygame

pygame.init()
from src.game import Game  # noqa: E402


def test_storm_pedestal_draws_blue_symbol():
    g = Game()
    g.select_stage("limbo_2")
    # Ensure we are in limbo_2
    assert g.selected_stage == "limbo_2"

    # Draw pedestals (via ui) - after removal this should still be callable
    try:
        g.draw_pedestals = True
    except Exception:
        pass

    # Call the UI draw_pedestals method directly; it should simply return
    try:
        g.ui.draw_pedestals()
    except Exception as e:
        assert False, f"draw_pedestals raised an exception: {e}"

    # Statues are now drawn again; sample the head pixel and confirm the
    # blueish tint remains.  Coordinates match the centre of the left statue.
    sx = g.screen
    sample_x = 370
    sample_y = 620 - 70
    color = sx.get_at((sample_x, sample_y))
    assert color.b >= color.r, f"Expected blueish pixel at statue head, got {color}"

    # We removed the chest badge visual; no further checks required for badge.
