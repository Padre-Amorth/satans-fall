from src.game import Game


def test_beast_increases_basic_projectile_radius():
    g = Game(debug=True)
    # Default multiplier -> base radius = int(8 * 1.0) == 8
    g.weapon_levels = {"beast": 1}
    g.player_weapons = ["beast"]

    g.fire_basic_weapon(1, 0)
    projs = list(g.projectiles)
    assert projs, "Expected at least one projectile"
    p = projs[-1]
    assert p.radius == int(8 * g.projectile_size_multiplier * 1.25)


def test_basic_projectile_radius_without_beast():
    g = Game(debug=True)
    g.weapon_levels = {"beast": 0}
    g.player_weapons = []

    g.fire_basic_weapon(1, 0)
    projs = list(g.projectiles)
    assert projs, "Expected at least one projectile"
    p = projs[-1]
    assert p.radius == int(8 * g.projectile_size_multiplier)
