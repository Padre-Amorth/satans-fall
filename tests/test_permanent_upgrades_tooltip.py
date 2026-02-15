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
