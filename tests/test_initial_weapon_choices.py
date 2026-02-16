from src.game import Game
from src.weapons import WEAPON_DEFS


def test_initial_weapon_choices_do_not_offer_purgatory_only_in_limbo():
    g = Game()
    # Ensure GameState default selected_stage can be set to limbo
    g.game_state.selected_stage = "limbo"

    # Run multiple times to sample randomness; none of the returned choices should be DemonStrike
    seen = set()
    for _ in range(40):
        choices = g.game_state.generate_initial_weapon_choices()
        ids = [c["id"] for c in choices]
        seen.update(ids)
        assert "DemonStrike" not in ids

    # Confirm DemonStrike exists in defs but was not sampled for limbo initial choices
    assert "DemonStrike" in WEAPON_DEFS


def test_initial_weapon_choices_may_include_demonstrike_in_purgatory():
    g = Game()
    # Use public API `select_stage` so GameStateManager is kept in sync
    g.select_stage("purgatory")

    found = False
    # Sample many times — DemonStrike should eventually appear in initial choices for purgatory
    for _ in range(80):
        choices = g.game_state.generate_initial_weapon_choices()
        ids = [c["id"] for c in choices]
        if "DemonStrike" in ids:
            found = True
            break
    assert found, "DemonStrike should be possible in Purgatory initial weapon choices"


def test_initial_weapon_choices_may_include_demonstrike_in_hell():
    g = Game()
    g.game_state.selected_stage = "hell"

    found = False
    # Sample many times — DemonStrike should eventually appear in initial choices for HELL
    for _ in range(80):
        choices = g.game_state.generate_initial_weapon_choices()
        ids = [c["id"] for c in choices]
        if "DemonStrike" in ids:
            found = True
            break
    assert found, "DemonStrike should be possible in HELL initial weapon choices"
