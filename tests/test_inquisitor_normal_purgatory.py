import pygame

from src.game import Game


def test_inquisitor_normal_spawns_and_is_limited(monkeypatch):
    pygame.init()
    g = Game(debug=True)
    g.select_stage("purgatory")
    em = g.enemy_manager

    # Make spawn deterministic: force random.random() -> 0.0 so spawn always succeeds
    monkeypatch.setattr("random.random", lambda: 0.0)

    # Ensure window reset
    em.inquisitor_spawn_window_timer = 0
    em.inquisitor_spawn_count = 0

    # Simulate three spawn checks (one per second) and ensure three inquisitor-lookalike normal enemies
    g.frame_count = g.fps  # align to second boundary
    em.update_inquisitor_spawns()

    g.frame_count += g.fps
    em.update_inquisitor_spawns()

    g.frame_count += g.fps
    em.update_inquisitor_spawns()

    inquisitors = [
        e
        for e in g.enemies
        if getattr(e, "appearance", None) == "inquisitor" and e.enemy_type == "normal"
    ]
    assert len(inquisitors) == 3

    # Fourth attempt within same 15s window should NOT spawn (cap enforced)
    g.frame_count += g.fps
    em.update_inquisitor_spawns()
    inquisitors = [
        e
        for e in g.enemies
        if getattr(e, "appearance", None) == "inquisitor" and e.enemy_type == "normal"
    ]
    assert len(inquisitors) == 3

    # Fast-forward window timer to expire and allow new spawns
    em.inquisitor_spawn_window_timer = 0
    em.inquisitor_spawn_count = 0
    g.frame_count += g.fps
    em.update_inquisitor_spawns()
    inquisitors = [
        e
        for e in g.enemies
        if getattr(e, "appearance", None) == "inquisitor" and e.enemy_type == "normal"
    ]
    assert len(inquisitors) >= 4
