from src.game import Game


def test_spawn_and_update():
    g = Game(debug=True)
    # Initially empty
    assert len(g.floating_texts) == 0

    # Spawn one
    g.spawn_floating_text(
        "5", 100, 50, color=(255, 255, 255), font_size=12, vy=-1.0, life=5
    )
    assert len(g.floating_texts) == 1

    ft = g.floating_texts[0]
    assert ft.text == "5"
    assert ft.x == 100
    assert ft.y == 50

    # Update repeatedly until it expires
    for _ in range(6):
        g._update_floating_texts()

    assert len(g.floating_texts) == 0
