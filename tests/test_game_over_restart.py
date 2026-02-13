import pygame

from src.game import Game


def test_game_over_restart_resets_run():
    game = Game(debug=True)
    game.select_stage("prologo")
    game.stage_start_countdown = 0
    # Simulate death
    game.player.health = 0
    game.update()

    assert game.showing_game_over is True

    # Modify some state so we can detect reset (e.g., spawn an enemy)
    game.spawn_enemy()
    # Ensure something exists to be cleared by reset
    assert len(list(game._enemies_iter())) > 0

    # Press Enter to restart
    game.handle_keydown(pygame.K_RETURN)

    # After restart, showing_game_over should be False and the run should be reset
    assert game.showing_game_over is False
    assert game.player.health == game.player.max_health
    # Enemies should have been cleared by reset_run inside select_stage
    assert len(list(game._enemies_iter())) == 0
    # The selected stage should remain the same
    assert game.selected_stage == "prologo"
