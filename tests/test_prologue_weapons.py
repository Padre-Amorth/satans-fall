#!/usr/bin/env python3
"""Test script to verify max weapons in Prologue and level 6 weapon choice"""

from src.game import Game


def test_prologue_max_weapons():
    print("Testing max weapons in Prologue...")

    # Create game instance
    game = Game()

    # Test default stage
    print(f"Default stage max_extra_weapons: {game.max_extra_weapons}")

    # Set to prologo
    game.selected_stage = "prologo"
    print(f"Prologo stage max_extra_weapons: {game.max_extra_weapons}")

    # Set to limbo
    game.selected_stage = "limbo"
    print(f"Limbo stage max_extra_weapons: {game.max_extra_weapons}")

    # Set to other
    game.selected_stage = "other"
    print(f"Other stage max_extra_weapons: {game.max_extra_weapons}")


def test_level_6_prologue_weapon_choice():
    print("\nTesting level 6 in Prologue with 2 weapons...")

    # Create game instance
    game = Game()
    game.selected_stage = "prologo"

    # Set up player with 2 weapons at level 5
    game.player_weapons = ["shotgun", "orbital"]
    game.weapon_levels = {"shotgun": 1, "orbital": 1}
    game.player_level = 5

    # Simulate level up to 6
    game.trigger_level_up()

    # At level 6 we must show only unowned weapon acquisition choices (up to 3)
    from src.weapons import WEAPON_DEFS

    unowned = [w for w in WEAPON_DEFS.keys() if w not in game.player_weapons]
    expected = min(3, len(unowned))
    assert game.awaiting_weapon_choice is True
    assert len(game.weapon_choices) == expected
    ids = [c["id"].replace("acquire_", "") for c in game.weapon_choices]
    assert len(set(ids)) == len(ids)  # unique
    for wid in ids:
        assert wid in unowned
        # Display name should be the weapon's name (no 'Acquire' prefix)
        expected_name = __import__("src.weapons", fromlist=["WEAPON_DEFS"]).WEAPON_DEFS[
            wid
        ]["name"]
        # Find the choice for this id
        choice = next((c for c in game.weapon_choices if c["id"].endswith(wid)), None)
        assert choice is not None
        assert choice["name"] == expected_name
        assert "description" in choice


if __name__ == "__main__":
    test_prologue_max_weapons()
    test_level_6_prologue_weapon_choice()
