from src.game import Game


def test_velocity_dampening_during_fade():
    g = Game(debug=True)
    # spawn with short life so fade phase is immediate
    g.spawn_floating_text("3", 10, 20, vy=-2.0, life=10)
    ft = g.floating_texts[0]

    # Advance until enters fade phase (life < max_life * 0.6)
    threshold = int(ft.max_life * 0.6)
    while ft.life >= threshold:
        ft.update()
    # In fade phase now: record vy, update once more and ensure magnitude decreases
    vy_before = ft.vy
    ft.update()
    vy_after = ft.vy
    assert abs(vy_after) < abs(vy_before)
