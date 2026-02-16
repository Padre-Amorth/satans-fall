import pygame

from src.game import Game


def test_inquisitor_normal_size_hp_and_shooting(monkeypatch):
    pygame.init()
    g = Game(debug=True)
    g.select_stage("purgatory")
    em = g.enemy_manager

    # Force spawn to happen
    monkeypatch.setattr("random.random", lambda: 0.0)

    # Align to second boundary so update_inquisitor_spawns may run
    g.frame_count = g.fps
    em.inquisitor_spawn_window_timer = 0
    em.inquisitor_spawn_count = 0

    em.update_inquisitor_spawns()

    inquisitors = [
        e
        for e in g.enemies
        if getattr(e, "appearance", None) == "inquisitor" and e.enemy_type == "normal"
    ]
    assert len(inquisitors) >= 1

    e = inquisitors[0]

    # Normal base width after Enemy.__init__ is 40 (30 + 10); inquisitor-normal should be +10 -> 50
    assert e.width >= 50

    # Health: spawn health=50 -> Enemy applies 1.2x -> 60, plus +10 tuning -> 70
    assert e.max_health >= 70

    # Test shooting: force immediate shot and verify slow projectile is produced
    # Ensure player is present
    player = g.player
    # Force shoot now
    e.shoot_cooldown = 0
    e.shoot_at_player(player, g)

    proj_found = any(
        getattr(p, "appearance", None) == "inquisitor"
        and getattr(p, "effect", None) == "slow"
        for p in g.enemy_projectiles
    )
    assert proj_found
