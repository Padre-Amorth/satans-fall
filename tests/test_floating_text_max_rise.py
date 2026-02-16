from src.game import FloatingText, Game


def run_updates_until_dead(ft: FloatingText) -> float:
    min_y = ft.y
    while ft.alive:
        ft.update()
        min_y = min(min_y, ft.y)
    return ft.initial_y - min_y


def test_floating_text_default_max_rise():
    g = Game()
    # spawn with defaults
    g.spawn_floating_text("10", 100, 100)
    assert len(g.floating_texts) == 1
    ft = g.floating_texts[0]

    rise = run_updates_until_dead(ft)
    # Default cap should be 12 pixels
    assert rise <= ft.max_rise_pixels
    assert rise <= 12


def test_floating_text_caps_even_with_high_velocity():
    # direct instantiate a high-velocity floating text
    ft = FloatingText("99", 100, 100, vy=-5.0, life=30, max_rise_pixels=12)
    rise = run_updates_until_dead(ft)
    assert rise <= 12


def test_spawned_text_respects_custom_max_rise():
    g = Game()
    # spawn via Game and then adjust last ft's max_rise
    g.spawn_floating_text("7", 50, 50, vy=-3.0, life=40)
    ft = g.floating_texts[-1]
    ft.max_rise_pixels = 6
    rise = run_updates_until_dead(ft)
    assert rise <= 6
