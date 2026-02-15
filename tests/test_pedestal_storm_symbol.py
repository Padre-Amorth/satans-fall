import pygame

pygame.init()
from src.game import Game  # noqa: E402


def test_storm_pedestal_draws_blue_symbol():
    g = Game()
    g.select_stage("limbo_2")
    # Ensure we are in limbo_2
    assert g.selected_stage == "limbo_2"

    # Draw pedestals (via ui)
    try:
        g.draw_pedestals = True
    except Exception:
        pass

    # Call the UI draw_pedestals method directly
    try:
        g.ui.draw_pedestals()
    except Exception as e:
        assert False, f"draw_pedestals raised an exception: {e}"

    # Sample pixel at left pedestal head area (approx coords from UI)
    sx = g.screen
    # Left pedestal head center at x=320, y ~ (620 - 70)
    sample_x = 320
    sample_y = 620 - 70
    try:
        color = sx.get_at((sample_x, sample_y))
    except Exception as e:
        assert False, f"Failed to sample screen pixel: {e}"

    # Expect the sampled pixel to be blueish (blue component >= red component)
    assert color.b >= color.r, f"Expected blueish pixel at pedestal head, got {color}"

    # We removed the chest badge visual; no further checks required for badge.
