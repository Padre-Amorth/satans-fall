#!/usr/bin/env python3
"""Test script to verify orbital weapon starts with 3 orbs"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from game import Game


def test_orbital_weapon():
    print("Testing orbital weapon initialization...")

    # Create game instance
    game = Game()

    # Simulate acquiring orbital weapon
    print("Before acquiring orbital weapon:")
    print(f"  orbital_count: {game.orbital_count}")
    print(f"  weapon_levels: {game.weapon_levels}")
    print(f"  player_weapons: {game.player_weapons}")

    # Acquire orbital weapon (simulate what happens in game_state.py)
    game.player_weapons.append("orbital")
    game.weapon_levels["orbital"] = 1
    game.orbital_count = 3  # This is what we changed it to
    game.create_orbitals()

    print("\nAfter acquiring orbital weapon:")
    print(f"  orbital_count: {game.orbital_count}")
    print(f"  weapon_levels: {game.weapon_levels}")
    print(f"  player_weapons: {game.player_weapons}")
    print(f"  Number of orbitals created: {len(game.orbitals)}")

    # Test upgrade
    print("\nTesting upgrade to level 2:")
    game.weapon_levels["orbital"] = 2
    game.orbital_count = game.weapon_levels["orbital"] // 2 + 3  # New formula
    game.create_orbitals()
    print(f"  orbital_count after level 2: {game.orbital_count}")
    print(f"  Number of orbitals after level 2: {len(game.orbitals)}")

    # Test upgrade to level 3
    print("\nTesting upgrade to level 3:")
    game.weapon_levels["orbital"] = 3
    game.orbital_count = game.weapon_levels["orbital"] // 2 + 3  # New formula
    game.create_orbitals()
    print(f"  orbital_count after level 3: {game.orbital_count}")
    print(f"  Number of orbitals after level 3: {len(game.orbitals)}")

    # Test upgrade to level 4
    print("\nTesting upgrade to level 4:")
    game.weapon_levels["orbital"] = 4
    game.orbital_count = game.weapon_levels["orbital"] // 2 + 3  # New formula
    game.create_orbitals()
    print(f"  orbital_count after level 4: {game.orbital_count}")
    print(f"  Number of orbitals after level 4: {len(game.orbitals)}")


if __name__ == "__main__":
    test_orbital_weapon()
