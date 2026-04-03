from src.game import Game


def test_execute_pause_option_sets_confirmation():
    g = Game(debug=True)
    g.paused = True
    g.pause_menu_option = 1  # Quit to Menu
    g.execute_pause_option()
    assert g.pause_confirmation is not None
    assert g.pause_confirmation["action"] == "quit"
    assert g.pause_confirmation["selection"] == 0


def test_mouse_click_yes_confirms_quit():
    g = Game(debug=True)
    # Simulate clicking Quit -> set confirmation
    g.paused = True
    g.pause_menu_option = 1
    g.execute_pause_option()
    assert g.pause_confirmation is not None

    # Click yes rect coordinates based on implementation
    dialog_w, dialog_h = 260, 70
    dx = g.width // 2 - dialog_w // 2
    dy = g.height // 2 - dialog_h // 2 + 20
    yes_x = dx + 10 + 5
    yes_y = dy + 30 + 5

    # Replace reset_game with a flag to observe it was called
    called = {"reset": False}
    orig = g.reset_game

    def fake_reset():
        called["reset"] = True

    g.reset_game = fake_reset

    g.handle_mouse_click((yes_x, yes_y), button=1)
    assert called["reset"] is True
    # restore
    g.reset_game = orig
