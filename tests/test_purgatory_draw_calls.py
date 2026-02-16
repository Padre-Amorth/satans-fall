from src.game import Game


def test_draw_calls_for_both_towers():
    g = Game()
    # Prepare stage and choices
    g.select_stage("purgatory")
    if g.weapon_choices:
        g.apply_weapon(g.weapon_choices[0]["id"])
    assert g.awaiting_tower_choice
    chosen = g.tower_choices[0]["id"]
    g.apply_tower(chosen)

    # Ensure towers exist and are visible
    assert getattr(g.left_tower, "tower_type", None) == chosen
    assert getattr(g.right_tower, "tower_type", None) == chosen
    assert getattr(g.left_tower, "visible", False) is True
    assert getattr(g.right_tower, "visible", False) is True

    calls = []
    orig = g.ui._draw_statue_model

    def wrapper(x, y, t, shake_x=0, shake_y=0):
        calls.append((int(x), int(y), t))
        return orig(x, y, t)

    g.ui._draw_statue_model = wrapper

    try:
        g.ui.draw_game_objects()
    finally:
        g.ui._draw_statue_model = orig

    # Check that wrapper was invoked for both left and right tower positions
    lx = int(g.left_tower.x + 0)
    ly = int(g.left_tower.y - 20)
    rx = int(g.right_tower.x + 0)
    ry = int(g.right_tower.y - 20)

    called_left = any(abs(cx - lx) <= 4 and abs(cy - ly) <= 4 for (cx, cy, t) in calls)
    called_right = any(abs(cx - rx) <= 4 and abs(cy - ry) <= 4 for (cx, cy, t) in calls)

    assert called_left, f"Left tower draw not called, calls={calls}"
    assert called_right, f"Right tower draw not called, calls={calls}"
