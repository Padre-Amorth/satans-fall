import pygame

from src.game import Game


def test_spawn_giant_and_boss_via_manager():
    pygame.init()
    g = Game(debug=True)
    em = g.enemy_manager
    assert em is not None

    # Spawn giant via Game helper (which should delegate)
    g.spawn_giant_enemy()
    giants = [e for e in g.enemies if getattr(e, "enemy_type", "") == "giant"]
    assert len(giants) >= 1

    # Spawn big boss via manager
    g.spawn_boss("big")
    bosses = [b for b in g.bosses if getattr(b, "enemy_type", "").startswith("boss_")]
    assert len(bosses) >= 1

    # Hell stage should replace giants with custodes
    g.selected_stage = "hell"
    g.spawn_system.last_giant_spawn_time = -20
    g.spawn_giant_enemy()
    custodes = [e for e in g.enemies if getattr(e, "enemy_type", "") == "custode"]
    assert custodes, "hell stage spawn_giant_enemy should produce a custode"

    # Manager should be tracking active instances (at least one giant or boss)
    tracked = any(
        getattr(e, "enemy_type", "").startswith("boss_")
        or getattr(e, "enemy_type", "") == "giant"
        for e in em.active
    )
    assert tracked


def test_spawn_crusader_via_manager():
    pygame.init()
    g = Game(debug=True)
    em = g.enemy_manager
    # The new helper should delegate properly
    g.spawn_crusader_enemy()
    crusaders = [e for e in g.enemies if getattr(e, "enemy_type", "") == "crusader"]
    assert crusaders, "spawn_crusader_enemy should create a crusader"

    # direct manager spawn with side parameter
    c = em.spawn_crusader_enemy(side="left")
    assert getattr(c, "enemy_type", "") == "crusader"
    assert c.x < 0


def test_spawn_giant_spawns_from_left_and_right():
    g = Game(debug=True)
    em = g.enemy_manager

    left = em.spawn_giant_enemy(side="left")
    assert getattr(left, "enemy_type", "") == "giant"
    assert left.x < 0
    assert 0 <= left.y <= g.height

    g.spawn_system.last_giant_spawn_time = -20
    right = em.spawn_giant_enemy(side="right")
    assert getattr(right, "enemy_type", "") == "giant"
    assert right.x > g.width
    assert 0 <= right.y <= g.height

    # On hell stage, side spawns should also respect custode replacement
    g.selected_stage = "hell"
    g.spawn_system.last_giant_spawn_time = -20
    left2 = em.spawn_giant_enemy(side="left")
    assert getattr(left2, "enemy_type", "") == "custode"
    g.spawn_system.last_giant_spawn_time = -20
    right2 = em.spawn_giant_enemy(side="right")
    assert getattr(right2, "enemy_type", "") == "custode"


def test_spawn_giant_default_spawns_from_top_inside_walls():
    g = Game(debug=True)
    em = g.enemy_manager
    # Call multiple times to exercise randomness; default should spawn from top inside walls
    for _ in range(20):
        g.spawn_system.last_giant_spawn_time = -20
        e = em.spawn_giant_enemy()
        assert getattr(e, "enemy_type", "") == "giant"
        # Default top spawn should start off-screen (y < 0) and x should be clamped inside walls
        assert e.y < 0
        assert 0 <= e.x <= g.width

    # double-check default behaviour on hell stage also produces custode
    g.selected_stage = "hell"
    for _ in range(5):
        g.spawn_system.last_giant_spawn_time = -20
        e = em.spawn_giant_enemy()
        assert getattr(e, "enemy_type", "") == "custode"
        assert e.y < 0
        assert 0 <= e.x <= g.width
