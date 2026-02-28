import pygame

from src.entities.enemy import Enemy
from src.game import Game


def test_winged_moves_toward_player():
    pygame.init()
    g = Game(debug=True)
    # place player at known coordinate
    g.player.x = 500
    g.player.y = 300

    w = Enemy(100, 100, enemy_type="winged", health=10, speed=120)

    # record initial distance
    initial_dist = ((w.x - g.player.x) ** 2 + (w.y - g.player.y) ** 2) ** 0.5
    # perform several updates and ensure distance decreases
    for _ in range(10):
        w.update(g.player, game=g)
    new_dist = ((w.x - g.player.x) ** 2 + (w.y - g.player.y) ** 2) ** 0.5
    assert (
        new_dist < initial_dist
    ), "winged enemy should be closer to player after updates"


def test_winged_zigzag_variation():
    pygame.init()
    g = Game(debug=True)
    g.player.x = 400
    g.player.y = 400
    w = Enemy(400, 0, enemy_type="winged", health=10, speed=120)
    w.update(g.player, game=g)
    # ensure x has changed slightly due to zigzag offset
    assert w.x != 400
