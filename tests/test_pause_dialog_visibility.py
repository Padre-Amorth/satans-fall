import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from game import Game


def test_pause_dialog_draws_without_error():
    g = Game()
    g.paused = True
    g.pause_menu_option = 1
    g.execute_pause_option()  # should set pause_confirmation
    assert g.pause_confirmation is not None

    # Drawing should not raise and should mark last drawn menu as pause
    g.ui.draw_pause_menu()
    assert getattr(g, "_last_drawn_menu", None) == "pause"
