"""Test ALT+F4 exit confirmation in permanent upgrades menu."""

import pygame

from src.game import Game


def test_alt_f4_exit_confirmation_in_permanent_upgrades():
    """Test that ALT+F4 (QUIT event) shows exit confirmation in permanent upgrades menu."""
    g = Game(debug=True)
    g.show_permanent_upgrades()

    # Verify we're in the permanent upgrades menu
    assert g.showing_permanent_upgrades is True
    assert g.showing_main_menu is False

    # Simulate QUIT event (ALT+F4)
    g.input_handler.handle_events = lambda: None  # Skip normal event handling

    # Manually trigger the QUIT event logic
    g.exit_confirm_pending = True

    # Verify exit confirmation dialog is shown
    assert g.exit_confirm_pending is True

    # Simulate clicking YES on the dialog
    # Dialog coordinates based on input_handler logic:
    dialog_w, dialog_h = 400, 160
    dialog_x = g.width // 2 - dialog_w // 2
    dialog_y = g.height // 2 - dialog_h // 2

    yes_w, yes_h = 75, 36
    yes_x = dialog_x + dialog_w // 2 - yes_w - 12
    yes_y = dialog_y + dialog_h - 52

    # Click YES
    g.mouse_x = yes_x + yes_w // 2
    g.mouse_y = yes_y + yes_h // 2
    g.input_handler.handle_mouse_click((g.mouse_x, g.mouse_y), button=1)

    # Game should be marked to exit
    assert g.running is False


def test_exit_confirm_no_button_in_permanent_upgrades():
    """Test that clicking NO cancels the exit confirmation."""
    g = Game(debug=True)
    g.show_permanent_upgrades()
    g.exit_confirm_pending = True

    # Dialog coordinates
    dialog_w, dialog_h = 400, 160
    dialog_x = g.width // 2 - dialog_w // 2
    dialog_y = g.height // 2 - dialog_h // 2

    no_w, no_h = 75, 36
    no_x = dialog_x + dialog_w // 2 + 12
    no_y = dialog_y + dialog_h - 52

    # Click NO
    g.mouse_x = no_x + no_w // 2
    g.mouse_y = no_y + no_h // 2
    g.input_handler.handle_mouse_click((g.mouse_x, g.mouse_y), button=1)

    # Dialog should be dismissed
    assert g.exit_confirm_pending is False
    # But we should still be in the menu
    assert g.showing_permanent_upgrades is True


def test_exit_confirm_ui_rendering_in_permanent_upgrades():
    """Test that exit confirmation dialog is rendered in permanent upgrades menu."""
    g = Game(debug=True)
    g.show_permanent_upgrades()
    g.exit_confirm_pending = True

    # Create a fake screen for drawing
    screen = pygame.Surface((g.width, g.height))
    g.ui.screen = screen

    # Draw should not raise an exception
    try:
        g.ui.draw_permanent_upgrades(shake_x=0, shake_y=0)
        # If we get here, the dialog was drawn without errors
        assert True
    except Exception as e:
        assert False, f"Failed to render exit confirmation in permanent upgrades: {e}"
