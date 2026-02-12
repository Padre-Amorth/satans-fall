import pygame

from src.game import Game


def test_spawn_inquisitor_on_limbo_wave():
    pygame.init()
    g = Game(debug=True)
    g.select_stage("limbo")
    em = g.enemy_manager

    # Simulate wave-time reaching boss spawn
    em.update_wave_boss(28)

    bosses = [b for b in g.bosses if getattr(b, "enemy_type", "") == "boss_inquisitor"]
    assert len(bosses) >= 1


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
        if getattr(p, "appearance", None) == "inquisitor" or getattr(p, "effect", None) == "slow":
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
    assert getattr(g.player, "slow_timer", 0) == 180
    # Player speed should be reduced by the slow_factor
    assert g.player.speed == orig_speed * getattr(g.player, "slow_factor", 1.0)
    # Verify slow strength was increased to the expected value
    assert getattr(g.player, "slow_factor", 1.0) == 0.4
