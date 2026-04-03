from src.game import Game


def test_spawn_defaults():
    g = Game(debug=True)
    g.spawn_floating_text("7", 10, 20)
    assert len(g.floating_texts) == 1
    ft = g.floating_texts[0]
    assert ft.color == (255, 255, 255)
    assert ft.font_size == 20
    assert ft.max_life == 70
