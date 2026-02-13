from src.game import Game


def test_game_over_stops_shaking():
    game = Game(debug=True)
    game.select_stage("prologo")

    # Simulate active screen shake
    game.shake_timer = 30
    game.shake_intensity = 10

    # Trigger death
    game.player.health = 0
    game.stage_start_countdown = 0
    game.stage_start_timer = 0

    game.update()

    # Game over should be active and shake_timer must be cleared
    assert game.showing_game_over is True
    assert game.shake_timer == 0
