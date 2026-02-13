import pytest

from src.game import Game
from src.weapons import WEAPON_DEFS


def test_level_6_purgatory_may_offer_demonstrike():
    g = Game()
    g.selected_stage = "purgatory"

    # Prepare player to level up to 6
    g.player_weapons = ["shotgun", "orbital"]
    g.weapon_levels = {"shotgun": 1, "orbital": 1}
    g.player_level = 5

    found = False
    # Sample multiple times: DemonStrike should eventually be in the choices for Purgatory
    for _ in range(60):
        g.trigger_level_up()
        if g.awaiting_weapon_choice:
            ids = [c["id"].replace("acquire_", "") for c in g.weapon_choices]
            if "DemonStrike" in ids:
                found = True
                break
        # reset to allow re-sampling in loop
        g.awaiting_weapon_choice = False
        g.weapon_choices = []
        g.player_level = 5

    assert found, "DemonStrike should be possible in level-6 weapon choices on Purgatory"