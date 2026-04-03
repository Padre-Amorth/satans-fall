"""Integration test for Blasphemy 5 Blink in actual gameplay."""

import pygame
import pytest

from src.game import Game


def complete_blink_animation(game):
    """Helper: complete the entire blink animation (pre-blink + invisible + post-blink)."""
    # Pre-blink: 10 frames + Invisible: 15 frames + Post-blink: 10 frames = 35 total
    for _ in range(35):
        game.update_blasphemy5_blink_animation()


def test_blink_works_in_limbo_gameplay():
    """Verify blink works when game is actively running in Limbo."""
    g = Game(debug=True)

    # Set up a proper game state
    g.selected_stage = "limbo"
    g.showing_main_menu = False
    g.showing_stage_menu = False
    g.paused = False
    g.awaiting_upgrade = False
    g.awaiting_weapon_choice = False
    g.awaiting_tower_choice = False

    # Give player blasphemy_5 and make them move
    g.permanent_stats["blasphemy_5"] = 1
    g.player.x = 640.0
    g.player.y = 360.0
    g.player.velocity_x = 200  # Moving right

    old_x = g.player.x

    # Simulate spacebar press
    g.input_handler.handle_keydown(pygame.K_SPACE)
    complete_blink_animation(g)

    # Blink should have happened
    assert g.player.x > old_x, "Player should have blinked to the right"
    assert g.player.x == pytest.approx(
        old_x + 120, abs=2
    ), "Blink distance should be ~120px"


def test_spacebar_ignored_during_pause():
    """Verify spacebar doesn't blink when game is paused."""
    g = Game(debug=True)

    g.selected_stage = "limbo"
    g.paused = True  # Game is paused
    g.permanent_stats["blasphemy_5"] = 1
    g.player.x = 640.0
    g.player.y = 360.0
    g.player.velocity_x = 200

    old_x = g.player.x

    # Spacebar during pause goes to pause menu, not blink
    g.input_handler.handle_keydown(pygame.K_SPACE)
    complete_blink_animation(g)

    # Player should not have blinked (spacebar handled by pause menu instead)
    assert g.player.x == old_x, "Spacebar should not trigger blink while paused"


def test_blink_blocked_during_upgrade_selection():
    """Verify spacebar does NOT trigger blink during upgrade selection."""
    g = Game(debug=True)

    g.selected_stage = "limbo"
    g.awaiting_upgrade = True
    g.upgrade_choices = [{"id": "damage"}]
    g.permanent_stats["blasphemy_5"] = 1
    g.player.x = 640.0
    g.player.y = 360.0
    g.player.velocity_x = 200

    old_x = g.player.x

    # Spacebar should NOT trigger blink during upgrade selection (disabled in input handler)
    g.input_handler.handle_keydown(pygame.K_SPACE)
    complete_blink_animation(g)

    # Player should not have blinked
    assert (
        g.player.x == old_x
    ), "Spacebar should not trigger blink during upgrade selection"
