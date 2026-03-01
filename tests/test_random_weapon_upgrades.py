#!/usr/bin/env python3
"""Test script to verify weapon upgrades are random in normal upgrades"""

import os
import sys


from game import Game


def test_random_weapon_upgrades():
    print("Testing random weapon upgrades in normal upgrades...")

    # Create game instance
    game = Game()

    # Set up player with weapons
    game.player_weapons = ["shotgun", "orbital"]
    game.weapon_levels = {"shotgun": 1, "orbital": 1}
    game.player_level = 4  # Level where normal upgrades are shown

    # Generate multiple sets of upgrade choices to check randomness
    weapon_upgrade_counts = []
    for i in range(10):
        upgrade_choices = game.generate_upgrade_choices()
        weapon_upgrades = [c for c in upgrade_choices if "upgrade" in c["id"]]
        weapon_upgrade_counts.append(len(weapon_upgrades))
        print(
            f"Run {i + 1}: {len(upgrade_choices)} choices, {len(weapon_upgrades)} weapon upgrades"
        )
        for choice in upgrade_choices:
            if "upgrade" in choice["id"]:
                print(f"  - {choice['name']}")

    print(f"\nWeapon upgrade counts across 10 runs: {weapon_upgrade_counts}")
    print(
        f"Average weapon upgrades per run: {sum(weapon_upgrade_counts) / len(weapon_upgrade_counts)}"
    )


if __name__ == "__main__":
    test_random_weapon_upgrades()
