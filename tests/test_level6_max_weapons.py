#!/usr/bin/env python3
"""Test script to verify level 6 weapon selection with max weapons"""

import pygame

from src.game import Game


def test_level_6_with_max_weapons():
    print("Testing level 6 with max weapons...")

    # Create game instance
    game = Game()

    # Set up player with max weapons at level 5 (will level up to 6)
    game.player_weapons = ["shotgun", "orbital"]
    game.weapon_levels = {"shotgun": 1, "orbital": 1}
    game.player_level = 5
    game.player_xp = game.xp_to_next_level  # To trigger level up

    # Test generate_weapon_upgrade_choices
    upgrades = game.generate_weapon_upgrade_choices()
    print(f"generate_weapon_upgrade_choices returned: {len(upgrades)}")
    for u in upgrades:
        print(f"  - {u['name']}")

    # Simulate level up
    game.trigger_level_up()

    print(f"awaiting_weapon_choice: {game.awaiting_weapon_choice}")
    print(f"awaiting_upgrade: {game.awaiting_upgrade}")
    print(f"len(weapon_choices): {len(game.weapon_choices)}")
    print(f"len(upgrade_choices): {len(game.upgrade_choices)}")

    print(f"At level 6 with {len(game.player_weapons)} weapons:")
    if game.awaiting_weapon_choice:
        print(f"Showing weapon choices: {len(game.weapon_choices)} options")
        for choice in game.weapon_choices:
            print(f"  - {choice['name']}: {choice['description']}")
    elif game.awaiting_upgrade:
        print(f"Showing upgrade choices: {len(game.upgrade_choices)} options")
        for choice in game.upgrade_choices:
            print(f"  - {choice['name']}: {choice['description']}")


if __name__ == "__main__":
    test_level_6_with_max_weapons()
