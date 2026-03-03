import os
import traceback

import pygame
import pytest

# Ensure headless test environment
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from src.game import Game


def test_draw_game_over_does_not_crash():
    game = Game(debug=True)
    game.permanent_stats["blasphemy_10"] = 0  # Disable revive
    game.select_stage("prologo")
    game.showing_main_menu = False  # Exit menu to allow gameplay updates
    game.stage_start_countdown = 0

    # Cause immediate death and make sure update triggers game over
    game.player.health = 0
    game.update()
    assert game.showing_game_over is True
    assert game.paused is True

    # Drawing the overlay should not raise
    try:
        game.draw_game_over()
        game.draw_ui()
    except Exception:
        traceback.print_exc()
        raise


def test_game_over_escape_returns_to_menu():
    game = Game(debug=True)
    game.permanent_stats["blasphemy_10"] = 0  # Disable revive
    game.select_stage("prologo")
    game.showing_main_menu = False  # Exit menu to allow gameplay updates
    game.stage_start_countdown = 0

    # Trigger game over
    game.player.health = 0
    game.update()
    assert game.showing_game_over is True

    # ESC should return to main menu
    game.handle_keydown(pygame.K_ESCAPE)
    assert game.showing_game_over is False
    assert game.showing_main_menu is True


def test_game_over_escape_with_stage_menu_left_open():
    """Regression: ESC must still wind up in the main menu even if the
    stage menu flag happened to be True when game over began (was seen with
    the FALL overlay).

    This reproduces the user-reported issue by forcing the erroneous state
    and ensures our input handler always short-circuits out early.
    """
    game = Game(debug=True)
    game.permanent_stats["blasphemy_10"] = 0  # Disable revive
    game.select_stage("prologo")
    game.showing_main_menu = False  # Exit menu to allow gameplay updates
    game.stage_start_countdown = 0

    # Trigger game over normally
    game.player.health = 0
    game.update()
    assert game.showing_game_over is True

    # simulate a stray stage menu appearing after death (the situation reported
    # by the user).  pressing ESC should still behave correctly.
    game.showing_stage_menu = True

    # Press ESC: should clear both flags and return to main menu
    game.handle_keydown(pygame.K_ESCAPE)
    assert game.showing_game_over is False
    assert game.showing_stage_menu is False
    assert game.showing_main_menu is True


def test_game_over_prevents_gameplay_updates():
    game = Game(debug=True)
    game.permanent_stats["blasphemy_10"] = 0  # Disable revive
    game.select_stage("prologo")
    game.showing_main_menu = False  # Exit menu to allow gameplay updates
    game.stage_start_countdown = 0

    # Set some gameplay values
    game.wave = 3
    game.score = 1234

    # Trigger game over
    game.player.health = 0
    game.update()
    assert game.showing_game_over is True

    # Call update multiple times; gameplay values should not change while showing_game_over
    for _ in range(10):
        prev_wave = game.wave
        prev_score = game.score
        game.update()
        assert game.wave == prev_wave
        assert game.score == prev_score


def test_blasphemy5_revive_auto_unpauses_and_draws():
    """Player death with Blasphemy 5 should trigger a timed pause and resume.

    Previous behaviour only attempted to auto-resume inside the victory overlay
    branch, which meant the game stayed paused indefinitely after the revive
    animation.  The game also used to crash if the draw/update loop ran while
    the pause flag was active.  This regression test exercises the entire
    revive sequence and ensures the game unpauses automatically without raising
    exceptions during the visual effect.
    """
    pygame.init()
    game = Game(debug=True)
    game.select_stage("prologo")
    game.showing_main_menu = False  # Exit menu to allow gameplay updates
    game.stage_start_countdown = 0

    # give the player the upgrade
    game.permanent_stats["blasphemy_10"] = 1

    # kill the player and run one frame to trigger revive
    game.player.health = 0
    game.update()
    assert game.blasphemy_5_revived is True
    assert game.paused is True
    assert game._paused_by_blasphemy5 is True
    assert game.blasphemy_5_pause_timer > 0
    assert game.player.health > 0, "Revive should restore some health"

    # step through the pause duration; draw() may be called while paused
    frames = int(game.fps * 2 + 5)
    for _ in range(frames):
        # update should not raise even while the game is paused
        game.update()
        try:
            game.draw()
        except Exception:
            pytest.fail("Drawing during blasphemy_5 animation crashed")

    # after the timer expires the game should have resumed automatically
    assert game.paused is False
    assert game._paused_by_blasphemy5 is False
