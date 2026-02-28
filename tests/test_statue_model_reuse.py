from src.game import Game


def test_statue_model_reuse_for_towers_and_pedestals():
    g = Game()

    # Ensure pedestal drawing in limbo renders a statue while limbo_final
    # remains empty (no static statues).
    for stage in ("limbo", "limbo_final"):
        g.select_stage(stage)
        # clear screen so previous stage artwork doesn't bleed in
        g.screen.fill((0, 0, 0))
        try:
            g.ui.draw_pedestals()
        except Exception as e:
            assert False, f"draw_pedestals raised in {stage}: {e}"
        # sample the head pixel; limbo_final should stay black
        from src import game_constants

        head_y = 620 - 10 - 70 + game_constants.STATUE_ASSET_VERTICAL_OFFSET
        pix = tuple(g.screen.get_at((370, head_y))[:3])
        if stage == "limbo":
            # assets may not load in test harness; at least something should be
            # drawn rather than pure black.
            assert pix != (
                0,
                0,
                0,
            ), f"Expected nonblack statue colour in {stage}, got {pix}"
        else:
            assert pix == (0, 0, 0), f"Expected no statue in {stage}, got {pix}"

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
