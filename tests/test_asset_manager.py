import pygame

from src.assets import manager as am


def test_get_image_caches(monkeypatch):
    calls = {"count": 0}

    def fake_load(path):
        calls["count"] += 1
        # Return a small surface; size doesn't matter for the test
        return pygame.Surface((8, 8))

    monkeypatch.setattr(pygame.image, "load", fake_load)

    am.clear_cache()

    img1 = am.get_image("projectile.png", (10, 10))
    img2 = am.get_image("projectile.png", (10, 10))

    assert calls["count"] == 1
    assert img1 is img2

    # Different size should produce a different scaled surface but still only one raw load
    img3 = am.get_image("projectile.png", (12, 12))
    assert calls["count"] == 1
    assert img3 is not img1

    am.clear_cache()


def test_get_image_missing(monkeypatch):
    def raise_load(path):
        raise FileNotFoundError("nope")

    monkeypatch.setattr(pygame.image, "load", raise_load)
    am.clear_cache()

    img = am.get_image("no_such.png", (10, 10))
    assert img is None

    am.clear_cache()
