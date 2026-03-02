#!/usr/bin/env python3
"""Test script to verify weapon upgrades in normal upgrades"""

from src.game import Game


def test_weapon_upgrades_in_normal_upgrades():
    print("Testing weapon upgrades in normal upgrades...")

    # Create game instance
    game = Game()

    # Set up player with weapons
    game.player_weapons = ["shotgun", "orbital"]
    game.weapon_levels = {"shotgun": 1, "orbital": 1}
    game.player_level = 4  # Level where normal upgrades are shown

    # Generate upgrade choices
    upgrade_choices = game.generate_upgrade_choices()
    print(
        f"At level 4 with weapons {game.player_weapons}, upgrade choices include {len(upgrade_choices)} options:"
    )
    for choice in upgrade_choices:
        print(f"  - {choice['name']}: {choice['description']}")

    # Check if any are weapon upgrades
    weapon_upgrade_choices = [c for c in upgrade_choices if "upgrade" in c["id"]]
    print(f"\nWeapon upgrade choices: {len(weapon_upgrade_choices)}")
    for choice in weapon_upgrade_choices:
        print(f"  - {choice['name']}: {choice['description']}")


if __name__ == "__main__":
    test_weapon_upgrades_in_normal_upgrades()
