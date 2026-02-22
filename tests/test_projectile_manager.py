import pygame

from src.game import Game
from src.projectile import FliesProjectile, Projectile


def test_spawn_and_recycle():
    pygame.init()
    g = Game(debug=True)
    pm = g.projectile_manager
    assert pm is not None

    # Spawn a basic projectile
    p = pm.spawn(100, 100, 10, 0, damage=5, radius=6)
    # It should be in game's projectiles container
    found = False
    try:
        for proj in g.projectiles:
            if proj is p:
                found = True
                break
    except Exception:
        if p in g.projectiles:
            found = True
    assert found

    # Kill the projectile (should recycle into pool)
    p.kill()

    # After kill and recycle, it should not be in active list and should be in a pool
    assert p not in pm.active
    assert p in pm.pool or p in pm.pool_flies


def test_register_existing_projectile():
    pygame.init()
    g = Game(debug=True)
    pm = g.projectile_manager

    p = Projectile(200, 200, 0, 0)
    # Add directly to game container
    try:
        g.projectiles.add(p)
    except Exception:
        g.projectiles.append(p)

    # Register with manager
    pm.register(p)
    assert p in pm.active

    # Recycle
    pm.recycle(p)
    assert p not in pm.active
    assert p in pm.pool or p in pm.pool_flies


def test_flies_pooling():
    pygame.init()
    g = Game(debug=True)
    pm = g.projectile_manager

    sd = pm.spawn(50, 50, 1, 1, weapon_type="Flies", damage=3)
    assert isinstance(sd, FliesProjectile)
    try:
        sd.kill()
    except Exception:
        pass
    assert sd not in pm.active
    assert sd in pm.pool_flies or sd in pm.pool
