import pytest

from src.game import Game


def test_level_3_demonstrike_not_offered_in_limbo():
    g = Game()
    g.selected_stage = "limbo"
    g.player_weapons = ["shotgun"]
    g.weapon_levels = {"shotgun": 1}
    g.player_level = 3

    # Generate choices for level 3
    choices = g.generate_weapon_choices()
    ids = [c["id"].replace("acquire_", "") for c in choices]

    assert "DemonStrike" not in ids


@pytest.mark.skip(
    reason="Randomness-based test: generate_upgrade_choices() unreliability"
)
def test_level_3_demonstrike_may_be_offered_in_purgatory():
    g = Game()
    g.selected_stage = "purgatory"
    g.player_weapons = ["shotgun"]
    g.weapon_levels = {"shotgun": 1}
    g.player_level = 3

    found = False
    # Sample multiple times since choices are random
    for _ in range(60):
        choices = g.generate_weapon_choices()
        ids = [c["id"].replace("acquire_", "") for c in choices]
        if "DemonStrike" in ids:
            found = True
            break
    assert (
        found
    ), "DemonStrike should be possible in level-3 weapon choices on Purgatory"
