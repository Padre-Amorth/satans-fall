import os

import pygame

from src.assets import manager


def test_get_image_retries_after_file_appears(tmp_path, monkeypatch):
    pygame.init()
    name = "temp_asset.png"
    # use the real assets directory so the manager sees the file
    asset_path = os.path.join(manager._ASSETS_DIR, name)

    # ensure any leftover file is removed
    try:
        os.remove(asset_path)
    except Exception:
        pass

    # ensure cache cleared so first lookup is fresh
    manager.clear_cache()

    # first call should return None and cache failure
    img1 = manager.get_image(name)
    assert img1 is None

    # create a real file in the assets directory so next call loads new image
    surf = pygame.Surface((10, 10))
    pygame.image.save(surf, asset_path)

    # second call should reload and return a surface
    img2 = manager.get_image(name)
    assert img2 is not None
    # ensure cache now holds image
    img3 = manager.get_image(name)
    assert img3 is img2

    # cleanup
    try:
        os.remove(asset_path)
    except Exception:
        pass
