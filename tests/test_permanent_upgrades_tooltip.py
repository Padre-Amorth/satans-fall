import os
from pathlib import Path

from src.game import Game


def setup_dummy_sdl():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def test_skill_tree_tooltip_shows_on_hover(tmp_path: Path) -> None:
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Open upgrades menu
    g.show_permanent_upgrades()

    # Position mouse over first FIRE left box (approx)
    left_x = g.width // 2 - 420
    separator_y = 320
    tree_top_y = separator_y - 150
    tree_box_w = 50
    tree_box_h = 36
    tree_base_x = left_x + 680
    # First tree (FIRE), first row -> left column
    col_x = tree_base_x
    inner_col_offset = tree_box_w // 2 + 1
    left_col_x = col_x - inner_col_offset
    row = 0
    y = tree_top_y + row * 46
    # Put mouse over the center of that box
    g.mouse_x = left_col_x
    g.mouse_y = y

    # Draw upgrades menu (should render tooltip)
    g.ui.draw_permanent_upgrades()

    # Check area under expected tooltip position (under trees)
    tip_x = col_x
    tip_y = tree_top_y + 3 * 46 + tree_box_h + 12

    # Sample small region around tip for any non-background pixel
    surf = g.screen
    bg = surf.get_at((0, 0))[:3]
    found = False
    for dx in range(-4, 5):
        for dy in range(-2, 3):
            x = max(0, min(surf.get_width() - 1, tip_x + dx))
            y = max(0, min(surf.get_height() - 1, tip_y + dy))
            if tuple(surf.get_at((x, y))[:3]) != tuple(bg):
                found = True
                break
        if found:
            break

    assert found, "Tooltip not rendered when hovering over skill tree box"


def test_blasphemy_tooltip_shows_on_hover(tmp_path: Path) -> None:
    """Hovering over the first blasphemy box shows a tooltip with description + levels."""
    setup_dummy_sdl()
    g = Game(permanent_stats_file=str(tmp_path / "permanent_stats.json"))

    # Ensure the first blasphemy has a visible level
    g.permanent_stats["blasphemy_1"] = 2

    g.show_permanent_upgrades()

    left_x = g.width // 2 - 420
    box_spacing = 100
    start_x = left_x + box_spacing // 2 - 40
    box_x = start_x + (0 * box_spacing)
    separator_y = 320
    box_y1 = separator_y + 80
    box_height = 80
    box_y2 = box_y1 + box_height + 20

    # Put mouse over the center of the first (top-left) blasphemy box
    g.mouse_x = box_x
    g.mouse_y = box_y1 + box_height // 2

    # Draw upgrades menu (should render the blasphemy tooltip)
    g.ui.draw_permanent_upgrades()
    surf = g.screen
    bg = tuple(surf.get_at((0, 0))[:3])

    # Tooltip is anchored under the blasphemies (below second row)
    tip_x = box_x
    tip_y = box_y2 + box_height + 12

    # Sample small region around tip for any non-background pixel
    found = False
    for dx in range(-4, 5):
        for dy in range(-2, 3):
            px = max(0, min(surf.get_width() - 1, tip_x + dx))
            py = max(0, min(surf.get_height() - 1, tip_y + dy))
            if tuple(surf.get_at((px, py))[:3]) != bg:
                found = True
                break
        if found:
            break

    assert found, "Blasphemy tooltip not rendered on hover"

    # Also ensure the level label inside the first box is visible
    sample_x = box_x
    sample_y = box_y1 + box_height // 2
    assert (
        tuple(surf.get_at((sample_x, sample_y))[:3]) != bg
    ), "Level text for blasphemy_1 not rendered"
