import pygame

from src.assets import manager as am
from src.game import Game


def test_limbo_boss_fallback_scales_to_width():
    pygame.init()
    # force missing asset by monkeypatching get_image
    original = am.get_image
    am.get_image = lambda name, size=None: None
    try:
        g = Game(debug=True)
        em = g.enemy_manager
        boss = em.spawn_boss("limbo")
        # check surface matches new width/height
        assert boss.image.get_width() == boss.width
        assert boss.image.get_height() == boss.height
        # ensure some non-transparent pixel exists (the purple ellipse)
        pixels = boss.image.get_at((boss.width // 2, boss.height // 2))
        assert pixels[3] != 0
    finally:
        am.get_image = original


def test_limbo_spawn_calls_draw_enemy(monkeypatch):
    """Spawning the limbo boss should invoke Enemy.draw_enemy instead of
    manually painting an ellipse.
    """
    pygame.init()
    called = {"hit": False}

    from src.entities.enemy import Enemy

    def fake_draw(self):
        called["hit"] = True

    monkeypatch.setattr(Enemy, "draw_enemy", fake_draw)
    g = Game(debug=True)
    g.enemy_manager.spawn_boss("limbo")
    assert called["hit"], "draw_enemy was not called during limbo boss spawn"


def test_limbo_horde_boss_uses_asset_when_present(tmp_path, monkeypatch):
    """The horde boss should also respect custom assets.

    Similar to the limbo-final test, we create a dummy sprite and ensure the
    spawned boss uses it instead of the built-in purple ellipse.
    """
    pygame.init()
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    img_path = assets_dir / "boss_limbo_horde.png"
    surf = pygame.Surface((120, 120))
    surf.fill((10, 200, 10))
    pygame.image.save(surf, str(img_path))

    from src.assets import manager as am

    monkeypatch.setattr(am, "_ASSETS_DIR", str(assets_dir), raising=False)

    g = Game(debug=True)
    boss = g.enemy_manager.spawn_boss("limbo_horde")
    # ensure spawn speed comes from balance table as expected
    from src.balance import ENEMY_BASE_SPEEDS

    assert abs(boss.speed - ENEMY_BASE_SPEEDS["boss_limbo_horde"]) < 1e-3

    cx = boss.width // 2
    cy = boss.height // 2
    # centre pixel should be primarily green (asset replaced)
    px = boss.image.get_at((cx, cy))
    assert px.g >= px.r and px.g >= px.b
    pygame.quit()


def test_limbo_boss_uses_asset_when_present(tmp_path, monkeypatch):
    """If a real boss_limbo.png is available the spawned boss should show it.

    We create a uniquely coloured dummy image and point the asset manager at
    it, then spawn and check the boss surface contains that colour instead of
    the usual purple fallback.
    """
    pygame.init()

    # prepare a dummy coloured file
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    img_path = assets_dir / "boss_limbo.png"
    surf = pygame.Surface((120, 120))
    surf.fill((123, 45, 67))
    pygame.image.save(surf, str(img_path))

    monkeypatch.setattr(am, "_ASSETS_DIR", str(assets_dir), raising=False)

    g = Game(debug=True)
    boss = g.enemy_manager.spawn_boss("limbo")
    # sample centre pixel - if asset was used it should match the colour above
    cx = boss.width // 2
    cy = boss.height // 2
    assert boss.image.get_at((cx, cy)) == (123, 45, 67, 255)
    # cleanup
    pygame.quit()
