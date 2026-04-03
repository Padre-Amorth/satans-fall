from src.game import Game


def test_health_drop_alpha_pulses():
    """The green health drop should be semi-transparent and pulse over time.

    The helper used by the renderer returns an alpha value that depends on
    ``game.frame_count``.  It should always be within the configured bounds and
    two different frame values ought to produce different results.
    """
    from src.ui import PygameUIManager

    g = Game()
    ui = PygameUIManager(g)

    drop = {"x": 42}
    # known bounds mirror the implementation (base=80, amplitude=80)
    min_alpha = 80
    max_alpha = 80 + 80

    g.frame_count = 0
    a1 = ui._health_drop_alpha(drop)
    assert min_alpha <= a1 <= max_alpha

    # advance frame count; result should change
    g.frame_count = 37
    a2 = ui._health_drop_alpha(drop)
    assert min_alpha <= a2 <= max_alpha
    assert a1 != a2

    # different x offset should shift phase
    drop2 = {"x": 500}
    g.frame_count = 37
    a3 = ui._health_drop_alpha(drop2)
    assert a3 != a2
