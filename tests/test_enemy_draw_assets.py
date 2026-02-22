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
