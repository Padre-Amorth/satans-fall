import pygame

from src.game import Game


def test_crusader_random_limit_per_wave():
    pygame.init()
    g = Game(debug=True)
    ss = g.spawn_system
    # stage must be purgatory or later for crusaders to appear
    g.selected_stage = "purgatory"
    ss.crusader_spawned_this_wave = 0

    # attempt many spawns; the counter should never exceed 5
    for _ in range(500):
        ss.spawn_enemy()
    assert ss.crusader_spawned_this_wave <= 5


def test_crusader_limit_resets_each_wave():
    pygame.init()
    g = Game(debug=True)
    ss = g.spawn_system
    g.selected_stage = "purgatory"
    # simulate some spawns earlier
    ss.crusader_spawned_this_wave = 3
    # trigger wave progression to reset counters
    g.wave_time = g.wave_duration
    g.update_wave_progression()
    assert ss.crusader_spawned_this_wave == 0


def test_crusader_not_allowed_before_purgatory():
    pygame.init()
    g = Game(debug=True)
    ss = g.spawn_system
    g.selected_stage = "prologo"
    ss.crusader_spawned_this_wave = 0
    for _ in range(500):
        ss.spawn_enemy()
    # no crusaders should ever be counted
    assert ss.crusader_spawned_this_wave == 0


def test_purgatory_variant_stage_allows_crusaders():
    pygame.init()
    g = Game(debug=True)
    ss = g.spawn_system
    # simulate a stage string with suffix
    for variant in ("purgatory1", "purgatory_1", "hell_2"):
        g.selected_stage = variant
        ss.crusader_spawned_this_wave = 0
        # force a bunch of spawns
        for _ in range(200):
            ss.spawn_enemy()
        # counter never exceeds limit (may be zero if unlucky)
        assert ss.crusader_spawned_this_wave <= 5

    # limbo variants should NOT allow crusaders
    for variant in ("limbo", "limbo_final", "limbo1"):
        g.selected_stage = variant
        ss.crusader_spawned_this_wave = 0
        for _ in range(200):
            ss.spawn_enemy()
        assert ss.crusader_spawned_this_wave == 0
