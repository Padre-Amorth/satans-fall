from src.game import Game


def test_towers_placed_outside_walls_and_draw_ok():
    g = Game()
    # Prepare stage
    g.select_stage("purgatory")
    # Simulate choosing weapon then tower
    if g.weapon_choices:
        g.apply_weapon(g.weapon_choices[0]["id"])
    assert g.awaiting_tower_choice
    # Choose tower
    chosen = g.tower_choices[0]["id"]
    g.apply_tower(chosen)

    # Towers should be configured
    assert getattr(g.left_tower, "tower_type", None) == chosen
    assert getattr(g.right_tower, "tower_type", None) == chosen

    # The x positions should be outside the walls at approximately the tower y
    left_wall_x = g._wall_x_at("left", g.left_tower.y)
    right_wall_x = g._wall_x_at("right", g.right_tower.y)
    assert g.left_tower.x < left_wall_x
    assert g.right_tower.x > right_wall_x

    # Drawing the game objects should not raise
    # Use ui draw_game_objects for a smoke test rendering
    try:
        g.ui.draw_game_objects()
    except Exception as e:
        assert False, f"draw_game_objects raised: {e}"
