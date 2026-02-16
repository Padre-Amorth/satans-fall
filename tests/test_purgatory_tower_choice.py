from src.game import Game


def test_purgatory_initial_tower_choice_flow():
    g = Game()

    # Select purgatory: both initial weapon and tower choices should be active
    g.select_stage("purgatory")
    assert g.awaiting_weapon_choice is True
    assert g.awaiting_tower_choice is True
    # Countdown shouldn't start before tower selection
    assert g.stage_start_countdown == 0

    # Apply a weapon choice (simulate player's selection)
    assert len(g.weapon_choices) > 0
    g.apply_weapon(g.weapon_choices[0]["id"])

    # After weapon chosen, weapon choice should be consumed and tower choice still waiting
    assert g.awaiting_weapon_choice is False
    assert g.awaiting_tower_choice is True
    # Countdown should still not have started
    assert g.stage_start_countdown == 0

    # Apply a tower choice (choose the first available)
    assert len(g.tower_choices) > 0
    chosen = g.tower_choices[0]["id"]
    g.apply_tower(chosen)

    # Tower choice should be consumed and towers configured accordingly
    assert g.awaiting_tower_choice is False
    assert getattr(g.left_tower, "tower_type", None) == chosen
    assert getattr(g.right_tower, "tower_type", None) == chosen

    # After both initial choices, countdown should start
    assert g.stage_start_countdown == 3
