import pygame

from src.game import Game

pygame.init()
g = Game(debug=True)
g.reset_game()
g.select_stage("limbo")
print("initial rate", g.enemy_manager.enemy_spawn_rate)
for i in range(1, 6):
    g.game_state.advance_wave()
    print(
        "wave",
        g.game_state.wave,
        "rate",
        g.enemy_manager.enemy_spawn_rate,
        "per10",
        600 / g.enemy_manager.enemy_spawn_rate,
    )
