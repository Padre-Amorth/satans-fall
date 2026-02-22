import os
from pathlib import Path

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def any_non_bg(surface, center, bg):
    x, y = center
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            px = max(0, min(surface.get_width() - 1, x + dx))
            py = max(0, min(surface.get_height() - 1, y + dy))
            if tuple(surface.get_at((px, py))[:3]) != tuple(bg):  # type: ignore[index]
                return True
    return False


def test_permanent_upgrades_shows_blasphemies_and_skill_trees(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Open upgrades menu and draw
    g.show_permanent_upgrades()
    g.ui.draw_permanent_upgrades()

    surface = g.screen
    bg = surface.get_at((0, 0))[:3]  # type: ignore[index]

    # subtitle used to be rendered at (left_x, 85).  With it gone, that point
    # should still be background color.  Sample a small region to avoid
    # accidental hits from nearby text.
    left_x = g.width // 2 - 420
    sub_x = left_x + 10
    sub_y = 85
    assert tuple(surface.get_at((sub_x, sub_y))[:3]) == bg, "Subtitle unexpected"

    # the main meta/satan label appears around y=110..120; scan a small
    # block of pixels to confirm that something other than background was drawn
    found_nonbg = False
    for dy in range(110, 125):
        for dx in range(0, 200, 10):
            px = left_x + dx
            if tuple(surface.get_at((px, dy))[:3]) != bg:
                found_nonbg = True
                break
        if found_nonbg:
            break
    assert found_nonbg, "SATAN LEVEL label not rendered (no non-bg pixels)"

    left_x = g.width // 2 - 420

    # Blasphemies title area (approx)
    blasphemies_point = (left_x + 4, 350)
    assert any_non_bg(surface, blasphemies_point, bg), "Blasphemies title not rendered"

    # Skill trees label area (FIRE expected on right side)
    fire_point = (left_x + 680, 142)
    assert any_non_bg(surface, fire_point, bg), "Skill tree labels not rendered"
