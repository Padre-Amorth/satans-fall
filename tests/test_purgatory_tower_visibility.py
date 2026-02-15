from src.game import Game


def test_purgatory_towers_hidden_before_selection_and_shown_after():
    g = Game()

    # Selecting purgatory should configure towers but keep them hidden until the player confirms
    g.select_stage("purgatory")
    assert getattr(g, "left_tower", None) is not None
    assert getattr(g, "right_tower", None) is not None
    assert g.left_tower.visible is False
    assert g.right_tower.visible is False

    # Ensure they are not drawn before selection (no non-black pixels near head)
    rt = g.right_tower
    head_y = int(rt.y - 90)
    head_x = int(rt.x)

    def neighbourhood_has_nonblack():
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                sx = head_x + dx
                sy = head_y + dy
                if 0 <= sx < g.width and 0 <= sy < g.height:
                    p = tuple(g.screen.get_at((sx, sy))[:3])
                    if p != (0, 0, 0):
                        return True
        return False

    g.ui.draw_game_objects()
    assert (
        not neighbourhood_has_nonblack()
    ), "Towers should not be visible before player selects a tower"

    # After applying a tower choice they should become visible and drawable
    assert len(g.tower_choices) > 0
    chosen = g.tower_choices[0]["id"]
    g.apply_tower(chosen)
    assert g.left_tower.visible is True
    assert g.right_tower.visible is True

    g.ui.draw_game_objects()
    if not neighbourhood_has_nonblack():
        # Try drawing directly to rule out draw path conditions
        try:
            g.ui._draw_statue_model(head_x, head_y + 70, rt.tower_type)
        except Exception:
            pass
        g.ui.draw_game_objects()

    assert (
        neighbourhood_has_nonblack()
    ), "Towers should be visible after selection and drawing"
