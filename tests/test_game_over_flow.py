import os
import traceback

import pygame

# Ensure headless test environment
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from src.game import Game


def test_draw_game_over_does_not_crash():
    game = Game(debug=True)
    game.select_stage("prologo")
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
    game.select_stage("prologo")
    game.stage_start_countdown = 0

    # Trigger game over
    game.player.health = 0
    game.update()
    assert game.showing_game_over is True

    # ESC should return to stage menu
    game.handle_keydown(pygame.K_ESCAPE)
    assert game.showing_game_over is False
    assert game.showing_stage_menu is True


def test_game_over_prevents_gameplay_updates():
    game = Game(debug=True)
    game.select_stage("prologo")
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
