#!/usr/bin/env python3
"""Test script to verify level 6 weapon upgrade choices"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from game import Game


def test_level_6_weapon_upgrades():
    print("Testing level 6 weapon upgrade choices...")

    # Create game instance
    game = Game()

    # Test 1: Player with max weapons (should only get upgrades)
    print("\n=== Test 1: Player with max weapons ===")
    game.player_weapons = ["shotgun", "orbital"]
    game.weapon_levels = {"shotgun": 2, "orbital": 3}
    game.player_level = 6

    weapon_upgrades = game.generate_weapon_upgrade_choices()
    print(f"Generated {len(weapon_upgrades)} weapon upgrade choices:")
    for upgrade in weapon_upgrades:
        print(f"  - {upgrade['name']}: {upgrade['description']}")

    game.trigger_level_up()
    print(
        f"At level 6 with max weapons, weapon choices include {len(game.weapon_choices)} options:"
    )
    for choice in game.weapon_choices:
        print(f"  - {choice['name']}: {choice['description']}")

    # Reset for next test
    game.awaiting_weapon_choice = False
    game.weapon_choices = []

    # Test 2: Player with 1 weapon (should get new weapons + upgrades)
    print("\n=== Test 2: Player with 1 weapon ===")
    game.player_weapons = ["shotgun"]
    game.weapon_levels = {"shotgun": 2}
    game.player_level = 6

    weapon_upgrades = game.generate_weapon_upgrade_choices()
    print(f"Generated {len(weapon_upgrades)} weapon upgrade choices:")
    for upgrade in weapon_upgrades:
        print(f"  - {upgrade['name']}: {upgrade['description']}")

    game.trigger_level_up()
    print(
        f"At level 6 with 1 weapon, weapon choices include {len(game.weapon_choices)} options:"
    )
    for choice in game.weapon_choices:
        print(f"  - {choice['name']}: {choice['description']}")

    # Test applying a weapon upgrade
    if weapon_upgrades:
        upgrade_id = weapon_upgrades[0]["id"]
        print(f"\nApplying weapon upgrade: {upgrade_id}")
        game.apply_weapon(upgrade_id)
        print(f"After upgrade - weapon_levels: {game.weapon_levels}")


if __name__ == "__main__":
    test_level_6_weapon_upgrades()
