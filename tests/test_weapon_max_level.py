#!/usr/bin/env python3
"""Test behavior around weapon max levels"""

from src.game import Game


def test_generate_weapon_upgrades_respects_max_level():
    game = Game()

    # If weapon is at level 5 and max is 6, an upgrade should be offered
    game.player_weapons = ["shotgun"]
    game.weapon_levels = {"shotgun": 5}
    upgrades = game.generate_weapon_upgrade_choices()
    assert any(
        u.get("id") == "shotgun_upgrade" for u in upgrades
    ), "Expected shotgun upgrade when at level 5"

    # If weapon is at max (6), no further upgrade for that weapon should be offered
    game.weapon_levels = {"shotgun": 6}
    upgrades = game.generate_weapon_upgrade_choices()
    assert not any(
        u.get("id") == "shotgun_upgrade" for u in upgrades
    ), "Did not expect shotgun upgrade when at max level"
