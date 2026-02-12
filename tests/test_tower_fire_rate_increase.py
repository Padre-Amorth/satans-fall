import pygame

from src.core.entities.tower import Tower
from src.game import Game
from src.balance import STATUE_FIRE_RATE


def test_tower_and_statue_fire_rate_increased():
    pygame.init()
    # Tower default fire_rate has been set to 85 per balance changes
    t = Tower(0, 0)
    assert getattr(t, 'fire_rate', None) == 85

    # Game statue_fire_rate should match updated STATUE_FIRE_RATE (85)
    g = Game(debug=True)
    assert getattr(g, 'statue_fire_rate', None) == STATUE_FIRE_RATE
    assert STATUE_FIRE_RATE == 85