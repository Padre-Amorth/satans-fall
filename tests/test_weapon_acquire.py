#!/usr/bin/env python3
"""Tests for acquiring weapons and default levels"""

from src.game import Game


def test_acquire_new_weapon_sets_level_and_orbitals():
    game = Game()

    # Ensure clean state
    game.player_weapons = []
    game.weapon_levels = {}

    # Acquire orbital via apply_weapon
    game.apply_weapon("orbital")

    assert "orbital" in game.player_weapons
    assert game.weapon_levels.get("orbital") == 1
    assert game.orbital_count == 3
    assert len(game.orbitals) == game.orbital_count


def test_generate_weapon_upgrade_choices_for_no_weapons_empty():
    game = Game()
    game.player_weapons = []
    game.weapon_levels = {}

    upgrades = game.generate_weapon_upgrade_choices()
    assert (
        upgrades == []
    ), "No upgrades should be proposed when the player has no weapons"
