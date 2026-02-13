#!/usr/bin/env python3
"""Test script to verify game reset functionality"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from game import Game


def test_game_reset():
    """Test that reset_game() properly resets all game state"""
    print("Testing game reset functionality...")

    # Create game instance
    game = Game()

    # Simulate a completed run with progress
    game.player_level = 5
    game.player_xp = 400
    game.xp_to_next_level = 500
    game.score = 10000
    game.difficulty_multiplier = 2.0
    game.player_weapons = ["shotgun", "orbital"]
    game.weapon_levels = {"shotgun": 3, "orbital": 2}
    game.upgrade_levels = {"damage": 2, "max_health": 1}
    game.permanent_stats = {"power": 1, "vigor": 1, "adrenaline": 1, "structure": 1}
    game.selected_stage = "limbo"

    print("Before reset:")
    print(f"  player_level: {game.player_level}")
    print(f"  player_xp: {game.player_xp}")
    print(f"  xp_to_next_level: {game.xp_to_next_level}")
    print(f"  score: {game.score}")
    print(f"  difficulty_multiplier: {game.difficulty_multiplier}")
    print(f"  player_weapons: {game.player_weapons}")
    print(f"  weapon_levels: {game.weapon_levels}")
    print(f"  upgrade_levels: {game.upgrade_levels}")
    print(f"  permanent_stats: {game.permanent_stats}")
    print(f"  selected_stage: {game.selected_stage}")
    print(f"  showing_stage_menu: {game.showing_stage_menu}")

    # Call reset_game() (what happens when quitting to menu)
    game.reset_game()

    print("\nAfter reset_game() (quit to menu):")
    print(f"  player_level: {game.player_level}")
    print(f"  player_xp: {game.player_xp}")
    print(f"  xp_to_next_level: {game.xp_to_next_level}")
    print(f"  score: {game.score}")
    print(f"  difficulty_multiplier: {game.difficulty_multiplier}")
    print(f"  player_weapons: {game.player_weapons}")
    print(f"  weapon_levels: {game.weapon_levels}")
    print(f"  upgrade_levels: {game.upgrade_levels}")
    print(f"  permanent_stats: {game.permanent_stats}")
    print(f"  selected_stage: {game.selected_stage}")
    print(f"  showing_stage_menu: {game.showing_stage_menu}")

    # Verify all values are reset correctly
    success = True
    checks = [
        (game.player_level == 1, "player_level should be 1"),
        (game.player_xp == 0, "player_xp should be 0"),
        (game.xp_to_next_level == 100, "xp_to_next_level should be 100"),
        (game.score == 0, "score should be 0"),
        (game.difficulty_multiplier == 1.0, "difficulty_multiplier should be 1.0"),
        (game.player_weapons == [], "player_weapons should be empty"),
        (game.weapon_levels == {}, "weapon_levels should be empty"),
        (
            game.upgrade_levels
            == {
                "damage": 0,
                "fire_rate": 0,
                "max_health": 0,
                "projectile_size": 0,
                "armor": 0,
            },
            "upgrade_levels should be reset",
        ),
        (
            game.permanent_stats
            == {"power": 0, "vigor": 0, "adrenaline": 0, "structure": 0},
            "permanent_stats should be reset",
        ),
        (game.selected_stage is None, "selected_stage should be None"),
        (game.showing_stage_menu, "showing_stage_menu should be True"),
    ]

    for check, message in checks:
        if not check:
            print(f"❌ FAIL: {message}")
            success = False
        else:
            print(f"✅ PASS: {message}")

    if success:
        print(
            "\n🎉 All reset checks passed! Game properly resets when returning to main menu."
        )
    else:
        print("\n💥 Some reset checks failed! Game state not properly reset.")

    assert success


if __name__ == "__main__":
    test_game_reset()
