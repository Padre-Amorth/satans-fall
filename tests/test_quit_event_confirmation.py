"""Test that pygame.QUIT event shows confirmation dialogs."""

import os
import sys

import pygame

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from game import Game


def test_quit_event_in_game_shows_pause_confirmation():
    """When X/ALT+F4 is pressed during gameplay, show pause_confirmation."""
    g = Game()
    g.select_stage("limbo")
    # Simulate pressing START button (hide main menu to show we're in-game)
    g.showing_main_menu = False
    g.showing_stage_menu = False
    assert g.selected_stage == "limbo"

    # Simulate pygame.QUIT event (X button or ALT+F4)
    # We'll call handle_events with a fake QUIT event
    quit_event = pygame.event.Event(pygame.QUIT)
    pygame.event.post(quit_event)

    # Process the event
    g.input_handler.handle_events()

    # Should show pause_confirmation with quit action
    assert g.pause_confirmation is not None
    assert g.pause_confirmation["action"] == "quit"
    assert g.pause_confirmation["selection"] == 0  # Yes is selected by default


def test_quit_event_in_menu_shows_exit_confirmation():
    """When X/ALT+F4 is pressed in main menu, show exit_confirm_pending."""
    g = Game()
    # Ensure we're in main menu
    assert g.showing_main_menu is True

    # Simulate pygame.QUIT event (X button or ALT+F4)
    quit_event = pygame.event.Event(pygame.QUIT)
    pygame.event.post(quit_event)

    # Process the event
    g.input_handler.handle_events()

    # Should set exit_confirm_pending instead of pause_confirmation
    assert g.exit_confirm_pending is True
    assert g.pause_confirmation is None


def test_quit_event_confirmation_accept_in_game():
    """Accept quit confirmation during gameplay should return to menu."""
    g = Game()
    g.select_stage("limbo")
    # Simulate pressing START button (hide main menu to show we're in-game)
    g.showing_main_menu = False
    g.showing_stage_menu = False

    # Simulate QUIT event
    quit_event = pygame.event.Event(pygame.QUIT)
    pygame.event.post(quit_event)
    g.input_handler.handle_events()

    # Should have pause_confirmation active
    assert g.pause_confirmation is not None

    # Press Y to confirm
    g.handle_keydown(pygame.K_y)

    # Should be back at main menu
    assert g.pause_confirmation is None
    assert g.showing_main_menu is True
    assert g.selected_stage is None


def test_quit_event_confirmation_cancel_in_game():
    """Cancel quit confirmation during gameplay should continue game."""
    g = Game()
    g.select_stage("limbo")
    g.paused = False
    # Simulate pressing START button (hide main menu to show we're in-game)
    g.showing_main_menu = False
    g.showing_stage_menu = False

    # Simulate QUIT event
    quit_event = pygame.event.Event(pygame.QUIT)
    pygame.event.post(quit_event)
    g.input_handler.handle_events()

    # Should have pause_confirmation active
    assert g.pause_confirmation is not None

    # Press N to cancel
    g.handle_keydown(pygame.K_n)

    # Should still be in game, pause_confirmation cleared
    assert g.pause_confirmation is None
    assert g.selected_stage == "limbo"
    assert g.showing_main_menu is False


def test_quit_event_confirmation_escape_in_game():
    """ESC should cancel quit confirmation during gameplay."""
    g = Game()
    g.select_stage("limbo")
    g.paused = False
    # Simulate pressing START button (hide main menu to show we're in-game)
    g.showing_main_menu = False
    g.showing_stage_menu = False

    # Simulate QUIT event
    quit_event = pygame.event.Event(pygame.QUIT)
    pygame.event.post(quit_event)
    g.input_handler.handle_events()

    # Should have pause_confirmation active
    assert g.pause_confirmation is not None

    # Press ESC to cancel
    g.handle_keydown(pygame.K_ESCAPE)

    # Should still be in game, pause_confirmation cleared
    assert g.pause_confirmation is None
    assert g.selected_stage == "limbo"
    assert g.showing_main_menu is False
