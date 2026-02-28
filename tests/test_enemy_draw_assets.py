import pygame

from src.entities.enemy import Enemy


def test_draw_enemy_uses_asset_if_available(monkeypatch):
    pygame.init()
    called = {}

    def fake_get_image(name, size=None):
        # record parameters and return a simple surface
        called["name"] = name
        called["size"] = size
        # return a surface with requested size (or default)
        w, h = size if size is not None else (20, 20)
        return pygame.Surface((w, h))

    # patch the asset manager function that draw_enemy imports
    import src.assets.manager as am

    monkeypatch.setattr(am, "get_image", fake_get_image)

    # create a custode enemy and force drawing
    e = Enemy(0, 0, "custode", health=100, speed=50)
    e.draw_enemy()

    assert called.get("name") == "enemy_custode.png", "Expected custode asset name"
    # the size should match the enemy dimensions
    assert called.get("size") == (e.width, e.height)

    # also verify that a mage uses the expected asset name and size
    called.clear()
    m = Enemy(0, 0, "mage", health=50, speed=30)
    m.draw_enemy()
    assert called.get("name") == "enemy_mage.png", "Expected mage asset name"
    # mage should now be 50x50 (+10 growth later to 60x60 after initialization)
    assert called.get("size") == (m.width, m.height)
    assert m.width >= 50 and m.height >= 50, "Mage dimensions should be at least 50x50"

    # and ensure our new limbo boss asset is requested when available
    called.clear()
    b = Enemy(0, 0, "boss_limbo", health=100, speed=40)
    b.draw_enemy()
    assert called.get("name") == "boss_limbo.png", "Expected limbo boss asset name"

    # horde boss asset should also be requested and uses distinct name
    called.clear()
    h = Enemy(0, 0, "boss_limbo_horde", health=100, speed=40)
    h.draw_enemy()
    assert (
        called.get("name") == "boss_limbo_horde.png"
    ), "Expected limbo horde boss asset name"

    # finally, winged enemy should attempt to load its own asset
    called.clear()
    w = Enemy(0, 0, "winged", health=30, speed=120)
    w.draw_enemy()
    assert called.get("name") == "enemy_winged.png", "Expected winged enemy asset name"

    # new crusader enemy should request its sprite if available
    called.clear()
    c = Enemy(0, 0, "crusader", health=100, speed=30)
    c.draw_enemy()
    assert called.get("name") == "enemy_crusader.png", "Expected crusader asset name"


def test_with_real_limbo_asset(tmp_path, monkeypatch):
    """If an actual file is placed in assets, Enemy.draw_enemy should load it.

    This test creates a small dummy PNG in the workspace assets folder and then
    runs through the normal drawing logic without mocking the asset manager.
    It verifies that the returned `image` matches the disk file dimensions.
    """
    import pygame

    from src.assets import manager as am
    from src.entities.enemy import Enemy

    pygame.init()
    # create a dummy image file in the assets directory
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    img_path = assets_dir / "boss_limbo.png"
    # create 120x120 surface and save
    surf = pygame.Surface((120, 120))
    pygame.image.save(surf, str(img_path))

    # monkeypatch module-level path used by asset manager (private variable)
    monkeypatch.setattr(am, "_ASSETS_DIR", str(tmp_path / "assets"), raising=False)
    # clear caches so previous test runs don't pollute results
    am.clear_cache()

    # asset manager should be able to load the file directly
    loaded = am.get_image("boss_limbo.png")
    assert loaded is not None, "Asset manager failed to load the dummy file"
    assert loaded.get_width() == 120 and loaded.get_height() == 120

    # drawing through Enemy should not crash and should still populate `.image`
    b = Enemy(0, 0, "boss_limbo", health=1, speed=0)
    b.draw_enemy()  # size may differ because enemies resize on creation
    assert hasattr(b, "image"), "Image should be stored on enemy"

    # horde boss should also draw (no crash) with its asset
    h = Enemy(0, 0, "boss_limbo_horde", health=1, speed=0)
    h.draw_enemy()
    assert hasattr(h, "image"), "Horde boss should also have an image"
    # cleanup pygame so subsequent tests aren't affected
    pygame.quit()


# also verify fallback behaviour when asset missing


def test_draw_enemy_fallback_when_missing(monkeypatch, caplog):
    pygame.init()

    def fake_get_image(name, size=None):
        return None  # simulate missing asset

    import src.assets.manager as am

    monkeypatch.setattr(am, "get_image", fake_get_image)
    e = Enemy(0, 0, "custode", health=100, speed=50)
    caplog.set_level("DEBUG")
    e.draw_enemy()  # should not raise
    # after drawing, image should be non-empty (fallback vector art)
    assert hasattr(e, "image") and e.image.get_width() > 0
