#!/usr/bin/env python3
"""Test script to verify level 3 weapon selection"""

from src.game import Game


def test_level_3_weapon_selection():
    print("Testing level 3 weapon selection...")

    # Create game instance
    game = Game()

    # Test: Player at level 3 with 1 weapon (should get new weapon choice)
    print("\n=== Test: Player at level 3 with 1 weapon ===")
    game.player_weapons = ["shotgun"]
    game.weapon_levels = {"shotgun": 1}
    game.player_level = 3

    # Simulate level up to trigger weapon choice
    # Since level 3 with 1 weapon should trigger weapon choice
    game.awaiting_weapon_choice = True
    game.weapon_choices = game.generate_weapon_choices()
    print(
        f"At level 3 with 1 weapon, weapon choices include {len(game.weapon_choices)} options:"
    )
    for choice in game.weapon_choices:
        print(f"  - {choice['name']}: {choice['description']}")

    # Test applying a weapon choice
    if game.weapon_choices:
        weapon_id = game.weapon_choices[0]["id"]
        print(f"\nApplying weapon choice: {weapon_id}")
        game.apply_weapon(weapon_id)
        print(f"After selection - player_weapons: {game.player_weapons}")
        print(f"After selection - weapon_levels: {game.weapon_levels}")


if __name__ == "__main__":
    test_level_3_weapon_selection()
