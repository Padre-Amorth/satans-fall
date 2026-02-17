import pygame

pygame.init()
pygame.font.init()

from src.game import Game  # noqa: E402
from src.projectile import Projectile  # noqa: E402


class SimpleEnemy:
    def __init__(self, x, y, speed=60):
        self.x = x
        self.y = y
        self.speed = speed


def test_apply_ice_puddles_slows_dict_and_object():
    g = Game()

    # object-based enemy (converted from former dict)
    d = SimpleEnemy(200, 150, speed=60)
    d.health = 10
    d.max_health = 10
    d.radius = 12

    # object-based enemy
    o = SimpleEnemy(200, 150, speed=80)

    g.enemies = [d, o]

    # single puddle centered on enemies with 50% slow
    g.ice_puddles = [
        {"x": 200, "y": 150, "radius": 50, "slow_factor": 0.5, "timer": 60}
    ]

    # Apply puddles
    g._apply_ice_puddles()

    # converted/simple enemy should have original_speed attribute and reduced speed
    assert hasattr(d, "original_speed")
    assert d.speed == d.original_speed * 0.5
    assert getattr(d, "slow_factor", None) == 0.5

    # object enemy should have original_speed attribute and reduced speed
    assert hasattr(o, "original_speed")
    assert o.speed == o.original_speed * 0.5
    assert o.slow_factor == 0.5


def test_remove_offscreen_projectiles_group_and_statue():
    g = Game()

    grp = pygame.sprite.Group()
    p = Projectile(100, -10, 0, 0)
    grp.add(p)
    g.projectiles = grp

    # Add two Projectile instances (one offscreen by y, one in-bounds)
    p_out = Projectile(10, -10, 0, 0)
    p_in = Projectile(50, 10, 0, 0)
    # Use a simple list to exercise list-branch in removal
    g.projectiles = [p_out, p_in]

    g._remove_offscreen_projectiles()

    # projectile list should only keep the in-bounds projectile
    assert len(g.projectiles) == 1
    remaining = g.projectiles[0]
    assert getattr(remaining, "x", None) == 50


def test_projectile_radius_helper_and_dict():
    g = Game()

    # Projectile object with explicit radius
    p_obj = Projectile(10, 10, 0, 0, radius=12)
    assert g._projectile_radius(p_obj) == 12

    # Projectile object with explicit radius
    p_obj2 = Projectile(10, 10, 0, 0, radius=8)
    assert g._projectile_radius(p_obj2) == 8

    # Projectile with rect but no radius
    class RectLike:
        def __init__(self, w):
            self.width = w

    class DummyProj:
        def __init__(self):
            self.rect = RectLike(30)

    dp = DummyProj()
    assert g._projectile_radius(dp) == 15


def test_get_projectile_metadata_normalization():
    g = Game()
    # ensure permanent upgrades do not affect normalization in this unit test
    g.permanent_stats["fire_2"] = 0

    # object-based projectile
    p = Projectile(0, 0, 0, 0)
    p.effect = "burn"
    p.slow_duration = 50
    p.slow_factor = 0.4
    p.burn_duration = 100
    p.burn_damage_per_second = 2.5
    meta = g._get_projectile_metadata(p)
    assert meta["effect"] == "burn"
    assert meta["slow_duration"] == 50
    assert abs(meta["slow_factor"] - 0.4) < 1e-6
    assert meta["burn_duration"] == 100
    assert abs(meta["burn_dps"] - 2.5) < 1e-6

    # object-based projectile
    p = Projectile(20, 20, 0, 0)
    p.effect = "slow"
    p.slow_duration = 30
    p.slow_factor = 0.6
    p.burn_duration = 80
    p.burn_damage_per_second = 1.5
    meta2 = g._get_projectile_metadata(p)
    assert meta2["effect"] == "slow"
    assert meta2["slow_duration"] == 30
    assert abs(meta2["slow_factor"] - 0.6) < 1e-6
    assert meta2["burn_duration"] == 80
    assert abs(meta2["burn_dps"] - 1.5) < 1e-6


def test_get_hit_enemies_for_projectile_with_list_and_group():
    g = Game()

    # List-based enemy (object)
    d = SimpleEnemy(200, 200, speed=60)
    d.radius = 12
    d.health = 10
    d.max_health = 10
    g.enemies = [d]
    g._build_spatial_grid()

    proj_obj = Projectile(200, 200, 0, 0, radius=5)
    hits = g._get_hit_enemies_for_projectile(proj_obj)
    assert d in hits

    # Group-based enemies (pygame Sprite)
    from src.entities.enemy import Enemy

    e = Enemy(300, 300)
    grp = pygame.sprite.Group()
    grp.add(e)
    g.enemies = grp
    g._build_spatial_grid()

    p_obj = Projectile(300, 300, 0, 0, radius=8)
    hits2 = g._get_hit_enemies_for_projectile(p_obj)
    assert e in hits2


def test_projectile_does_not_hit_when_outside_collision_radius():
    """Regression: projectile must NOT damage an enemy when placed beyond (pr + er).

    This verifies we don't reuse stale candidate lists and that the plain-list
    collision pass only reports overlaps when the center distance is <= sum of radii.
    """
    from src.entities.enemy import Enemy

    g = Game(debug=True)
    enemy = Enemy(200, 200)
    g.enemies = [enemy]

    pr = 5
    # place projectile 3 pixels beyond collision boundary
    p = Projectile(200 + (pr + enemy.radius) + 3, 200, 0, 0, damage=10, radius=pr)

    try:
        g.projectiles.empty()
    except Exception:
        g.projectiles = []
    try:
        g.projectiles.append(p)
    except Exception:
        g.projectiles = [p]

    before_hp = enemy.health
    g.handle_collisions()

    # No damage should have occurred and projectile must not have recorded a hit
    assert enemy.health == before_hp
    assert id(enemy) not in getattr(p, "_hit_ids", set())


def test_enemy_kill_is_idempotent_and_records_game():
    from src.entities.enemy import Enemy

    g = Game()
    e = Enemy(100, 100)

    # Ensure initial counter
    assert getattr(g, "enemies_killed_this_run", 0) == 0

    # Kill twice — should only increment once
    e.kill()
    e.kill()

    assert g.enemies_killed_this_run == 1
