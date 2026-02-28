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
    g = Game()
    # give some XP so the green fill is visible during rendering
    g.global_progress["meta_xp"] = 1

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

    # Sanity check: some gold pixels should appear in the meta area.  We'll
    # look for at least two distinct horizontal rows of gold text (level +
    # points).  The points row should coincide with the bar's y-coordinate.
    gold = (255, 215, 0)
    found_rows = set()
    for dy in range(90, 135):
        for dx in range(0, 300, 5):
            px = left_x + dx
            if tuple(surface.get_at((px, dy))[:3]) == gold:
                found_rows.add(dy)
                break
    assert len(found_rows) >= 2, (
        "Expected two separate gold text rows for level and points,"
        " saw {len(found_rows)}"
    )

    # determine bar_y and bar_x by first looking for the green fill pixel
    # (when XP > 0).  This prevents grabbing some other dark-grey region as
    # the bar background, which previously yielded a misleading x value.
    bar_y = None
    bar_x = None
    _bar_w = 180  # match UI constant
    for dy in range(110, 135):
        for dx in range(0, g.width):
            if tuple(surface.get_at((dx, dy))[:3]) == (0, 100, 0):
                bar_y = dy
                bar_x = dx
                break
        if bar_y is not None:
            break
    # if no green pixel was found (xp == 0), fall back to locating the grey
    # background instead.
    if bar_y is None:
        for dy in range(110, 135):
            for dx in range(0, g.width, 5):
                if tuple(surface.get_at((dx, dy))[:3]) == (26, 26, 26):
                    bar_y = dy
                    bar_x = dx
                    break
            if bar_y is not None:
                break
    assert bar_y is not None, "Unable to locate XP bar on screen"

    # bar should share vertical position with the Points text as before.
    assert any(
        abs(bar_y - r) <= 1 for r in found_rows
    ), "XP bar should share a vertical position with the Points text"
    # bar should still be reasonably to the right of left_x (but not too far)
    assert bar_x < left_x + 220, "XP bar not in expected horizontal range near Points"

    # ensure the progress bar doesn't overlap the POWER stat (y≈140).
    power_y = 140
    assert (
        tuple(surface.get_at((bar_x + 10, power_y))[:3]) == bg
    ), "XP bar overlaps POWER; it should sit above the stats area"

    # verify fill color is the updated darker green at least once inside
    # the bar width (when xp>0).
    if g.global_progress.get("meta_xp", 0) > 0:
        assert any(
            tuple(surface.get_at((bar_x + x, bar_y))[:3]) == (0, 100, 0)
            for x in range(0, 200)
        ), "XP bar fill is not the expected darker green"

    # xp text should remain at its original location; since the bar moved
    # right by 20px, the gap between bar and text should now be at least 70px.
    xp_x = None
    for dx in range(bar_x + 1, g.width):
        for dy in range(bar_y - 2, bar_y + 3):
            if tuple(surface.get_at((dx, dy))[:3]) == (255, 215, 0):
                xp_x = dx
                break
        if xp_x is not None:
            break
    assert xp_x is not None, "Unable to locate XP text"
    assert xp_x - bar_x >= 70, f"XP text moved with bar; gap {xp_x - bar_x} < 70"
    left_x = g.width // 2 - 420

    # Blasphemies title area (approx)
    blasphemies_point = (left_x + 4, 350)
    assert any_non_bg(surface, blasphemies_point, bg), "Blasphemies title not rendered"

    # Skill trees label area (FIRE expected on right side)
    fire_point = (left_x + 680, 142)
    assert any_non_bg(surface, fire_point, bg), "Skill tree labels not rendered"
