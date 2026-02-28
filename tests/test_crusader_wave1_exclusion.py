"""Test that crusaders don't spawn in wave 1."""

import pygame

from src.game import Game


def test_no_crusaders_in_wave1():
    """Verify that crusaders never spawn in the first wave."""
    pygame.init()
    g = Game(debug=True)
    ss = g.spawn_system

    for stage in ["purgatory", "hell"]:
        g.selected_stage = stage
        g.wave = 1  # explicitly set to wave 1
        ss.crusader_spawned_this_wave = 0

        # spawn many enemies in wave 1
        for _ in range(500):
            ss.spawn_enemy()

        print(f"[{stage} Wave 1] Crusaders spawned: {ss.crusader_spawned_this_wave}")
        assert (
            ss.crusader_spawned_this_wave == 0
        ), f"No crusaders allowed in wave 1 of {stage}"


def test_crusaders_allowed_wave2_onward():
    """Verify that crusaders CAN spawn from wave 2 onwards."""
    pygame.init()
    g = Game(debug=True)
    ss = g.spawn_system

    for stage in ["purgatory", "hell"]:
        g.selected_stage = stage
        g.wave = 2  # wave 2 and beyond allow crusaders
        ss.crusader_spawned_this_wave = 0

        # spawn many enemies in wave 2+
        for _ in range(1000):
            ss.spawn_enemy()

        print(f"[{stage} Wave 2+] Crusaders spawned: {ss.crusader_spawned_this_wave}")
        assert (
            ss.crusader_spawned_this_wave > 0
        ), f"Crusaders should appear in wave 2+ of {stage}"
