#!/usr/bin/env python3
"""Test script to verify max weapons in Limbo and level 6 weapon choice"""

from src.game import Game


def test_limbo_max_weapons():
    print("Testing max weapons in Limbo...")

    # Create game instance
    game = Game()

    # Test default stage
    print(f"Default stage max_extra_weapons: {game.max_extra_weapons}")

    # Set to limbo
    game.selected_stage = "limbo"
    print(f"Limbo stage max_extra_weapons: {game.max_extra_weapons}")

    # Set to limbo_2
    game.selected_stage = "limbo_2"
    print(f"Limbo_2 stage max_extra_weapons: {game.max_extra_weapons}")

    # Set to prologo
    game.selected_stage = "prologo"
    print(f"Prologo stage max_extra_weapons: {game.max_extra_weapons}")


def test_level_6_limbo_weapon_choice():
    print("\nTesting level 6 in Limbo with 2 weapons...")

    # Create game instance
    game = Game()
    game.selected_stage = "limbo"

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
    from src.weapons import WEAPON_DEFS as WD

    # DemonStrike is Purgatory‑only and must not be proposed in Limbo level‑6 choices
    assert "DemonStrike" not in ids

    for wid in ids:
        assert wid in unowned
        expected_name = WD[wid]["name"]
        choice = next((c for c in game.weapon_choices if c["id"].endswith(wid)), None)
        assert choice is not None
        assert choice["name"] == expected_name
        assert "description" in choice


if __name__ == "__main__":
    test_limbo_max_weapons()
    test_level_6_limbo_weapon_choice()
