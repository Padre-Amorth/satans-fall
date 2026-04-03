"""Test that screen shake is fully reset when returning to main menu."""

import pygame

from src.game import Game


def test_shake_reset_on_return_to_menu():
    """Verify that screen shake (timer and intensity) is reset when returning to main menu."""
    pygame.init()
    g = Game(debug=True)

    # Start a game
    g.selected_stage = "hell"
    g.showing_stage_menu = False

    # Simulate some screen shake from combat
    g.shake_timer = 50
    g.shake_intensity = 10

    # Verify shake is active
    assert g.shake_timer > 0, "shake_timer should be active"
    assert g.shake_intensity > 0, "shake_intensity should be active"

    # Call reset_run() to simulate exiting a game
    g.reset_run()

    # Both shake_timer and shake_intensity should be reset to 0
    assert g.shake_timer == 0, "shake_timer should be reset to 0"
    assert g.shake_intensity == 0, "shake_intensity should be reset to 0"

    pygame.quit()


def test_reset_game_clears_shake():
    """Verify that reset_game() returns to main menu without residual shake."""
    pygame.init()
    g = Game(debug=True)

    # Start a game
    g.selected_stage = "hell"
    g.showing_stage_menu = False
    g.showing_main_menu = False

    # Simulate screen shake
    g.shake_timer = 50
    g.shake_intensity = 10

    # Call reset_game() which calls reset_run()
    g.reset_game()

    # Both should be reset
    assert g.shake_timer == 0, "shake_timer should be reset after reset_game()"
    assert g.shake_intensity == 0, "shake_intensity should be reset after reset_game()"
    assert g.showing_main_menu is True, "Should be back at main menu"

    pygame.quit()
