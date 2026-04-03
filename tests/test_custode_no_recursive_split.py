import pygame

from src.game import Game


def test_custode_halves_do_not_split_again():
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "hell"

    # spawn and cause split
    g.spawn_giant_enemy()
    halves = [e for e in g.enemies if getattr(e, "enemy_type", "") == "custode"]
    assert len(halves) == 1
    big = halves[0]
    big.take_damage(int(big.max_health * 0.71))
    try:
        big.update(g.player, g)
    except Exception:
        pass

    halves = [e for e in g.enemies if getattr(e, "enemy_type", "") == "custode"]
    assert len(halves) == 2

    # damage one of the halves to half health again - should not produce more
    half = halves[0]
    before = len([e for e in g.enemies if getattr(e, "enemy_type", "") == "custode"])
    half.take_damage(half.max_health // 2 + 1)
    after = len([e for e in g.enemies if getattr(e, "enemy_type", "") == "custode"])
    assert after == before, "split halves should not spawn additional enemies"
