import os
from pathlib import Path

import pygame

from src.assets import manager as am
from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_blasphemy_boxes_use_imported_asset(tmp_path: Path) -> None:
    """If an asset named `blasphemy_box.png` exists in `assets/`,
    all Blasphemy boxes use it as scaled background."""
    setup_dummy_sdl()

    # create a distinctive image in the project's assets folder
    repo_assets = Path(__file__).resolve().parents[1] / "assets"
    repo_assets.mkdir(parents=True, exist_ok=True)
    asset_path = repo_assets / "blasphemy_box.png"

    pygame.init()
    surf = pygame.Surface((80, 60))
    color = (12, 111, 222)
    surf.fill(color)
    pygame.image.save(surf, str(asset_path))

    # clear asset cache so the new file is visible to AssetManager
    am.clear_cache()

    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))
    g.show_permanent_upgrades()
    g.ui.draw_permanent_upgrades()

    # sample a pixel in the center of the first top-row blasphemy box
    left_x = g.width // 2 - 420
    box_spacing = 100
    start_x = left_x + box_spacing // 2 - 40
    box_x = start_x + (0 * box_spacing)
    box_y1 = 320 + 80
    box_height = 80

    sample_x = box_x
    sample_y = box_y1 + box_height // 2
    sampled = tuple(g.screen.get_at((sample_x, sample_y))[:3])

    assert (
        sampled == color
    ), "Blasphemy boxes should render the imported asset as background"

    # cleanup
    try:
        asset_path.unlink()
    except Exception:
        pass
    am.clear_cache()
