import itertools
from unittest.mock import patch

import pygame

from src.game import Game


def test_shielded_replaces_strong_in_non_prologo():
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "limbo"  # non-prologo stage
    # control random.random so first call selects strong, second triggers shield
    rnd = itertools.cycle(
        [0.05, 0.1]
    )  # first <0.10->strong (wave default 0), second <0.30 -> shield
    with patch("random.random", side_effect=lambda: next(rnd)):
        g.spawn_enemy()
    types = [e.enemy_type for e in g.enemies]
    assert "shielded" in types, "Expected shielded variant spawned"


def test_no_shield_in_prologo():
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "prologo"
    rnd = itertools.cycle([0.05, 0.1])
    with patch("random.random", side_effect=lambda: next(rnd)):
        g.spawn_enemy()
    types = [e.enemy_type for e in g.enemies]
    assert "shielded" not in types, "Prologo should not spawn shielded enemies"
    assert "strong" in types, "Should still spawn strong in prologo with same random"
