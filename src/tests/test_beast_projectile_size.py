# ensure project root is on path when running this test directly
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

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


def test_beast_projectile_shows_6(monkeypatch):
    import pygame

    from src.projectile import Projectile

    pygame.init()
    called = {}

    class FakeFont:
        def __init__(self, *args, **kwargs):
            pass

        def render(self, text, antialias, color):
            called["text"] = text
            return pygame.Surface((1, 1))

    monkeypatch.setattr("pygame.font.Font", FakeFont)
    p = Projectile(0, 0, 0, 0, radius=5, weapon_type="beast", appearance="beast")
    p.draw_projectile()
    assert called.get("text") == "6", "Beast projectile should render '6'"
