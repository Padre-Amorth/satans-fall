from src.game import Game


def test_statue_model_reuse_for_towers_and_pedestals():
    g = Game()

    # Ensure pedestal drawing in limbo works (no exceptions)
    g.select_stage("limbo")
    try:
        g.ui.draw_pedestals()
    except Exception as e:
        assert False, f"draw_pedestals raised: {e}"

    # Now select purgatory and pick each tower type and draw
    g.select_stage("purgatory")
    # consume weapon choice to move to tower choice
    if g.weapon_choices:
        g.apply_weapon(g.weapon_choices[0]["id"])
    assert g.awaiting_tower_choice

    for t in ["fire", "storm", "ice"]:
        # re-open tower choices if cleared
        if not g.tower_choices:
            try:
                g.game_state.show_initial_tower_choice()
                g.awaiting_tower_choice = g.game_state.awaiting_tower_choice
                g.tower_choices = list(g.game_state.tower_choices)
            except Exception:
                g.tower_choices = g.generate_initial_tower_choices()
        # pick appropriate id matching 't'
        # find index
        idx = None
        for i, tc in enumerate(g.tower_choices):
            if tc["id"] == t:
                idx = i
                break
        assert idx is not None
        g.apply_tower(t)
        # drawing should succeed
        try:
            g.ui.draw_game_objects()
        except Exception as e:
            assert False, f"draw_game_objects raised for tower {t}: {e}"
