import os

# set dummy SDL driver for reliable headless test runs
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from src.game import Game


def test_game_over_persists_until_keypress():
    # Create game and select a stage so update runs game loop code paths
    game = Game(debug=True)
    game.select_stage("prologo")

    # Simulate player death
    game.player.health = 0
    # Bypass the initial stage countdown so update proceeds immediately
    game.stage_start_countdown = 0
    game.stage_start_timer = 0

    # Update should detect death and enter game over state
    game.update()
    assert game.showing_game_over is True

    # If a USEREVENT+2 timer fires while game over is active, it should be ignored
    pygame.event.post(pygame.event.Event(pygame.USEREVENT + 2))
    game.handle_events()
    assert game.showing_game_over is True

    # Pressing RETURN should do nothing (restart disabled); ESC returns to the main menu
    game.handle_keydown(pygame.K_RETURN)
    assert game.showing_game_over is True

    # Pressing ESC should return to main menu
    game.handle_keydown(pygame.K_ESCAPE)
    assert game.showing_main_menu is True
    assert game.selected_stage is None


def test_game_over_fade_in():
    game = Game(debug=True)
    game.select_stage("prologo")
    game.stage_start_countdown = 0
    game.player.health = 0
    game.update()
    assert game.showing_game_over is True
    # After one update the alpha should have begun increasing
    assert game.game_over_alpha > 0
    # Simulate frames until fully faded (bounded loop to avoid infinite loops)
    for _ in range(300):
        game.update()
        if game.game_over_alpha >= 255:
            break
    assert game.game_over_alpha == 255
