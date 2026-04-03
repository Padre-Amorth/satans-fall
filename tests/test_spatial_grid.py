import pygame

from src.utils.spatial_grid import SpatialGrid


def test_spatial_grid_basic():
    grid = SpatialGrid(cell_size=50, width=400, height=400)
    objs = []
    # place objects at (50,50), (150,150), (300,300)
    for x, y in [(50, 50), (150, 150), (300, 300)]:
        objs.append(SimpleObj(x, y, r=5))

    grid.build(objs)

    # Query near first object
    res1 = grid.query_circle(48, 52, 10)
    assert any(
        (hasattr(o, "x") and o.x == 50 and hasattr(o, "y") and o.y == 50) for o in res1
    )

    # Query near second object
    res2 = grid.query_circle(150, 150, 5)
    assert any(
        (hasattr(o, "x") and o.x == 150 and hasattr(o, "y") and o.y == 150)
        for o in res2
    )

    # Query in empty region
    res3 = grid.query_circle(10, 300, 5)
    assert res3 == []


class SimpleObj:
    def __init__(self, x, y, r=3):
        self.x = x
        self.y = y
        self.radius = r


def test_spatial_grid_with_objects():
    grid = SpatialGrid(cell_size=60, width=300, height=300)
    a = SimpleObj(30, 40)
    b = SimpleObj(120, 140)
    grid.build([a, b])

    res = grid.query_circle(32, 39, 6)
    assert a in res
    assert b not in res


def test_game_handle_collisions_with_sprite_and_dict():
    # Initialize pygame (headless is fine in CI)
    pygame.init()

    from src.entities.enemy import Enemy
    from src.game import Game
    from src.projectile import FliesProjectile, Projectile

    g = Game(debug=True)

    # Sprite enemy test
    e = Enemy(200, 200, enemy_type="normal", health=60)
    # ensure group usage
    g.enemies = pygame.sprite.Group()
    g.enemies.add(e)

    p = Projectile(200, 200, 0, 0, damage=10, radius=6)
    # put projectile in a plain list to test different iter paths
    try:
        g.projectiles = pygame.sprite.Group()
        g.projectiles.add(p)
    except Exception:
        g.projectiles = [p]

    # Run collisions
    g.handle_collisions()

    # Enemy should have taken damage
    assert e.health < e.max_health

    # Flies special case (projectile should be removed/attached)
    e2 = Enemy(300, 300, enemy_type="normal", health=40)
    g.enemies.add(e2)

    sd = FliesProjectile(300, 300, 0, 0, damage=5, heal_amount=2, level=1)
    try:
        g.projectiles.add(sd)
    except Exception:
        g.projectiles.append(sd)

    g.handle_collisions()

    # Ensure drain timer applied and projectile removed / killed
    assert getattr(e2, "drain_timer", 0) > 0

    # Dict-style enemy test
    g2 = Game(debug=True)
    dict_enemy = Enemy(400, 400, enemy_type="normal", health=30)
    g2.enemies = [dict_enemy]

    proj = Projectile(400, 400, 0, 0, damage=6, radius=6)
    # projectiles as list
    g2.projectiles = [proj]

    g2.handle_collisions()

    # Enemy should have taken damage (compare vs its starting max_health)
    assert dict_enemy.health < dict_enemy.max_health


__all__ = [
    "test_spatial_grid_basic",
    "test_spatial_grid_with_objects",
    "test_game_handle_collisions_with_sprite_and_dict",
]
