from src.game import Game


def _rect_points(rect):
    """Return corner and center points inside the given pygame.Rect"""
    pts = []
    # small inset to ensure we're inside the rect
    inset = 3
    pts.append((rect.x + inset, rect.y + inset))  # top-left
    pts.append((rect.x + rect.w - inset, rect.y + inset))  # top-right
    pts.append((rect.x + inset, rect.y + rect.h - inset))  # bottom-left
    pts.append((rect.x + rect.w - inset, rect.y + rect.h - inset))  # bottom-right
    pts.append((rect.x + rect.w // 2, rect.y + rect.h // 2))  # center
    return pts


def test_yes_box_click_positions_trigger_reset():
    from pygame import Rect

    dialog_w, dialog_h = 260, 70

    # generate a new game for each point so state is clean
    # compute dx/dy using same logic as UI/game
    for _ in range(3):
        g = Game(debug=True)
        g.paused = True
        g.pause_menu_option = 1
        g.execute_pause_option()

        dx = g.width // 2 - dialog_w // 2
        dy = g.height // 2 - dialog_h // 2 + 20
        yes_rect = Rect(dx + 10, dy + 30, 80, 28)

        points = _rect_points(yes_rect)

        for p in points:
            # prepare a fresh confirmation for each point
            g.pause_confirmation = {"action": "quit", "selection": 0}
            called = {"reset": False}

            orig = g.reset_game

            def fake_reset():
                called["reset"] = True

            g.reset_game = fake_reset

            g.handle_mouse_click(p, button=1)
            assert called["reset"] is True, f"Click at {p} did not trigger reset"

            # restore
            g.reset_game = orig


def test_no_box_click_positions_cancel_confirmation():
    from pygame import Rect

    dialog_w, dialog_h = 260, 70

    g = Game(debug=True)
    g.paused = True
    g.pause_menu_option = 1
    g.execute_pause_option()

    dx = g.width // 2 - dialog_w // 2
    dy = g.height // 2 - dialog_h // 2 + 20
    no_rect = Rect(dx + dialog_w - 80 - 10, dy + 30, 80, 28)

    points = _rect_points(no_rect)

    for p in points:
        # set confirmation
        g.pause_confirmation = {"action": "quit", "selection": 0}
        called = {"reset": False}

        orig = g.reset_game

        def fake_reset():
            called["reset"] = True

        g.reset_game = fake_reset

        g.handle_mouse_click(p, button=1)

        # clicking No should not call reset, and should clear confirmation
        assert called["reset"] is False, f"Click at {p} erroneously triggered reset"
        assert (
            g.pause_confirmation is None
        ), f"Click at {p} did not clear pause_confirmation"

        # restore
        g.reset_game = orig
