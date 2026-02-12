import pygame

from src.core.entities.tower import Tower
from src.game import Game
from src.balance import STATUE_FIRE_RATE


def test_tower_and_statue_fire_rate_increased():
    pygame.init()
    # Tower default fire_rate should be 220 / 1.5 -> ~146
    t = Tower(0, 0)
    assert getattr(t, 'fire_rate', None) == 146

    # Game statue_fire_rate should match updated STATUE_FIRE_RATE (~98)
    g = Game(debug=True)
    assert getattr(g, 'statue_fire_rate', None) == STATUE_FIRE_RATE
    assert STATUE_FIRE_RATE == 98