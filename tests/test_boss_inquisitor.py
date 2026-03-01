import pygame

from src.game import Game


def test_spawn_inquisitor_on_limbo_wave():
    pygame.init()
    g = Game(debug=True)
    g.select_stage("limbo")
    em = g.enemy_manager

    # Any wave in Limbo should spawn an inquisitor boss only
    for wave in (1, 3, 6):
        try:
            g.bosses.empty()
        except Exception:
            g.bosses = []
        g.wave = wave
        em.wave_boss_spawned = False
        em.update_wave_boss(38)
        bosses = [
            b for b in g.bosses if getattr(b, "enemy_type", "") == "boss_inquisitor"
        ]
        assert len(bosses) >= 1, f"expected inquisitor on limbo wave {wave}"
        # make sure no big boss sneaked in
        assert not any(
            b.enemy_type == "boss_big" for b in g.bosses
        ), "boss_big must not spawn on limbo"


def test_legacy_spawn_system_never_creates_big_in_limbo():
    """When the EnemyManager is absent the fallback logic must also avoid
    boss_big on limbo stages.
    """
    pygame.init()
    g = Game(debug=True)
    # remove manager to force fallback path
    g.enemy_manager = None
    g.select_stage("limbo")
    # simulate a wave where the normal logic would try to spawn a boss
    g.wave = 3
    g.wave_time = 38.0
    g.wave_boss_spawned = False

    # wave boss logic occurs during wave progression rather than plain
    # enemy spawning. call the helper directly the same way the main loop
    # would.
    g.update_wave_progression()

    bosses = [b for b in g.bosses if hasattr(b, "enemy_type")]
    assert bosses, "expected some boss to spawn via legacy path"
    # limbo stages should never produce boss_big
    assert all(
        b.enemy_type != "boss_big" for b in bosses
    ), "legacy path spawned boss_big"
    # with the fallback now supporting inquisitors, we should see one
    assert any(
        b.enemy_type == "boss_inquisitor" for b in bosses
    ), "expected inquisitor instead"


def test_inquisitor_projectile_slows_player_on_hit():
    pygame.init()
    g = Game(debug=True)
    # Spawn an inquisitor directly via manager
    boss = g.enemy_manager.spawn_boss("inquisitor")
    # Place boss close enough to player for reliable aiming
    boss.x = g.player.x
    boss.y = g.player.y - 80

    # Ensure player baseline
    orig_speed = g.player.speed

    # Force the boss to shoot at player
    boss.shoot_at_player(g.player, g)

    # There should be at least one enemy projectile created
    assert len(g.enemy_projectiles) > 0
    # Grab any inquisitor projectile and simulate immediate hit
    proj = None
    for p in g.enemy_projectiles:
        if (
            getattr(p, "appearance", None) == "inquisitor"
            or getattr(p, "effect", None) == "slow"
        ):
            proj = p
            break
    assert proj is not None

    # Move projectile onto player and update its rect so sprite-collision detects it
    proj.x = g.player.x
    proj.y = g.player.y
    try:
        proj.rect.center = (proj.x, proj.y)
    except Exception:
        pass
    g.handle_collisions()

    # Projectile should be removed and player should be slowed (stronger & longer)
    # slow duration should match the new 1.5 second value (90 frames at 60fps)
    assert getattr(g.player, "slow_timer", 0) == int(1.5 * g.fps)
    # Player speed should be reduced by the slow_factor
    assert g.player.speed == orig_speed * getattr(g.player, "slow_factor", 1.0)
    # Verify slow strength was increased to the expected value
    assert getattr(g.player, "slow_factor", 1.0) == 0.4


def test_inquisitor_alternates_fire_pattern():
    pygame.init()
    g = Game(debug=True)
    boss = g.enemy_manager.spawn_boss("inquisitor")
    boss.x = g.player.x
    boss.y = g.player.y - 120

    # clear any existing projectiles
    try:
        g.enemy_projectiles.empty()
    except Exception:
        g.enemy_projectiles = []

    # First shot -> should be a 3-shot spread
    boss.shoot_at_player(g.player, g)
    projectiles = []
    for p in g.enemy_projectiles:
        if (
            getattr(p, "appearance", None) == "inquisitor"
            or getattr(p, "effect", None) == "slow"
        ):
            projectiles.append(p)
    assert len(projectiles) == 3
    # verify spread angle ≈ 30.6° (previously ~28.6° before widening)
    import math

    angles = []
    for proj in projectiles:
        dx = proj.vel_x
        dy = proj.vel_y
        angles.append(math.atan2(dy, dx))
    angles.sort()
    total_arc_deg = math.degrees(angles[-1] - angles[0])
    assert 29 <= total_arc_deg <= 32, f"expected ~30° spread, got {total_arc_deg:.1f}°"

    # Clear and shoot again -> should be a single shot
    try:
        g.enemy_projectiles.empty()
    except Exception:
        g.enemy_projectiles = []
    boss.shoot_at_player(g.player, g)
    count_second = 0
    for p in g.enemy_projectiles:
        if (
            getattr(p, "appearance", None) == "inquisitor"
            or getattr(p, "effect", None) == "slow"
        ):
            count_second += 1
    assert count_second == 1

    # Third shot -> should alternate back to 3
    try:
        g.enemy_projectiles.empty()
    except Exception:
        g.enemy_projectiles = []
    boss.shoot_at_player(g.player, g)
    count_third = 0
    for p in g.enemy_projectiles:
        if (
            getattr(p, "appearance", None) == "inquisitor"
            or getattr(p, "effect", None) == "slow"
        ):
            count_third += 1
    assert count_third == 3
