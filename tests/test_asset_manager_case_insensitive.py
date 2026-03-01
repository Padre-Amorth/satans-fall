import os
import pygame

from src import assets


def test_get_image_case_insensitive(tmp_path, monkeypatch):
    # monkeypatch asset dir to temporary location
    monkeypatch.setattr(assets, "_ASSETS_DIR", str(tmp_path))
    assets.clear_cache()

    # create a dummy file with uppercase name
    fname = "TeNeBrAe.PNG"
    surf = pygame.Surface((10, 5), pygame.SRCALPHA)
    pygame.image.save(surf, os.path.join(str(tmp_path), fname))

    # requesting with lowercase should succeed
    got = assets.get_image("tenebrae.png")
    assert got is not None

    # requesting with prefix should also succeed
    got2 = assets.get_image("weapon_tenebrae.PNG")
    assert got2 is not None
