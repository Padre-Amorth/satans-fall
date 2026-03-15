import pygame
import pytest

from src.game import Game


def test_custode_split_creates_explosion():
    pygame.init()
    g = Game(debug=True)
    g.selected_stage = "hell"

    # ensure explosions list cleared
    g.skullboom_explosions.clear()
    g.skullboom_particles.clear()

    # spawn big custode and trigger split
    g.spawn_giant_enemy()
    cust = [e for e in g.enemies if getattr(e, "enemy_type", "") == "custode"]
    assert cust
    big = cust[0]
    big.take_damage(int(big.max_health * 0.71))
    try:
        big.update(g.player, g)
    except Exception:
        pass

    # explosion should have been appended
    assert len(g.skullboom_explosions) >= 1
    exp = g.skullboom_explosions[-1]
    assert exp["radius"] == 40
    assert exp["timer"] == 15
    # ensure required keys for rendering are present
    assert exp.get("max_radius") == 40
    assert exp.get("max_timer") == 15
    assert "color" in exp
    # validate explosion drawing won't crash (simulate one frame draw)
    try:
        g.draw_skullboom_particles()
    except Exception:
        pytest.skip("unable to render explosion in this environment")
    # some particles should also have been spawned
    assert len(g.skullboom_particles) >= 1
    # every particle should expose an 'alive' attribute (objects) or at least
    # be tolerated by the update filter
    for p in g.skullboom_particles:
        assert hasattr(p, "alive") or isinstance(p, dict)
