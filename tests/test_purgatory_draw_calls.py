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
    # unlock special by activating the center skill for this tower type
    g.permanent_stats[f"{chosen}_7"] = 1

    # Ensure towers exist and are visible
    assert getattr(g.left_tower, "tower_type", None) == chosen
    assert getattr(g.right_tower, "tower_type", None) == chosen
    assert getattr(g.left_tower, "visible", False) is True
    assert getattr(g.right_tower, "visible", False) is True

    calls = []
    calls_bar = []
    orig = g.ui._draw_statue_model
    orig_bar = getattr(g.ui, "_draw_tower_energy_bar", None)

    def wrapper(x, y, t, shake_x=0, shake_y=0):
        calls.append((int(x), int(y), t))
        return orig(x, y, t)

    def bar_wrapper(shake_x=0, shake_y=0):
        calls_bar.append(True)
        if orig_bar:
            return orig_bar(shake_x, shake_y)

    g.ui._draw_statue_model = wrapper
    if hasattr(g.ui, "_draw_tower_energy_bar"):
        g.ui._draw_tower_energy_bar = bar_wrapper

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
    # energy bar should also have been drawn at least once
    assert calls_bar, "Energy bar draw not invoked"

    # bar should be visible even when empty (background or border non-black)
    # sample a pixel near bottom of the vertical bar
    bar_x = g.ui.width - 16 - 20 + 2
    bar_y = g.ui.height - 4 - 20  # a few pixels above bottom
    pixel = tuple(g.screen.get_at((bar_x, bar_y))[:3])
    assert pixel != (0, 0, 0), f"Bar pixel should not be black, got {pixel}"


def test_no_bar_when_special_locked():
    g = Game()
    g.select_stage("purgatory")
    if g.weapon_choices:
        g.apply_weapon(g.weapon_choices[0]["id"])
    chosen = g.tower_choices[0]["id"]
    g.apply_tower(chosen)
    # ensure unlock is not present
    g.permanent_stats[f"{chosen}_7"] = 0

    calls_bar = []
    orig_bar = getattr(g.ui, "_draw_tower_energy_bar", None)

    def bar_wrapper(shake_x=0, shake_y=0):
        calls_bar.append(True)
        if orig_bar:
            return orig_bar(shake_x, shake_y)

    if hasattr(g.ui, "_draw_tower_energy_bar"):
        g.ui._draw_tower_energy_bar = bar_wrapper
    # perform a draw
    g.ui.draw_game_objects()
    assert not calls_bar, "Energy bar should not draw when special locked"


def test_no_bar_in_prologo_even_if_energy_and_unlock(monkeypatch):
    # energy/unlock shouldn’t force bar in prologo stage
    g = Game()
    g.select_stage("prologo")
    # artificially grant stats and energy
    g.permanent_stats["fire_7"] = 1
    g.tower_energy = g.tower_energy_max
    calls_bar = []
    orig_bar = getattr(g.ui, "_draw_tower_energy_bar", None)

    def bar_wrapper(shake_x=0, shake_y=0):
        calls_bar.append(True)
        if orig_bar:
            return orig_bar(shake_x, shake_y)

    if hasattr(g.ui, "_draw_tower_energy_bar"):
        g.ui._draw_tower_energy_bar = bar_wrapper
    g.ui.draw_game_objects()
    assert not calls_bar, "Energy bar must never render in prologo"
