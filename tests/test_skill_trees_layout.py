#!/usr/bin/env python3
"""Tests for the new 2-column + center layout and unlocking rules for skill trees."""

from src.game import Game


def coords_for_tree(g: Game, col_index: int, tier_index: int):
    """Return a click coordinate for element column col_index (0..2) and tier_index 1..7.
    tier_index 1..3 => left column rows 1..3
    tier_index 4..6 => right column rows 1..3 (mapped 4->row0)
    tier_index 7 => center bottom"""
    left_x = g.width // 2 - 420
    separator_y = 320
    tree_base_x = left_x + 680
    tree_col_spacing = 120
    tree_box_w = 50
    tree_box_h = 36
    tree_v_spacing = 46
    tree_top_y = separator_y - 150

    col_x = tree_base_x + col_index * tree_col_spacing
    inner_col_offset = tree_box_w // 2 + 1
    left_col_x = col_x - inner_col_offset
    right_col_x = col_x + inner_col_offset

    if 1 <= tier_index <= 3:
        row = tier_index - 1
        x = left_col_x
        y = tree_top_y + row * tree_v_spacing + tree_box_h // 2
    elif 4 <= tier_index <= 6:
        row = tier_index - 4
        x = right_col_x
        y = tree_top_y + row * tree_v_spacing + tree_box_h // 2
    elif tier_index == 7:
        x = col_x
        y = tree_top_y + 3 * tree_v_spacing + tree_box_h // 2
    else:
        raise ValueError("invalid tier")
    return (x, y)


def test_center_unlock_requires_full_column():
    g = Game()
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    # Ensure both columns empty
    for i in range(1, 8):
        g.permanent_stats[f"fire_{i}"] = 0

    # Try to unlock center (should fail)
    pos_center = coords_for_tree(g, 0, 7)
    g.handle_mouse_click(pos_center, button=1)
    assert g.permanent_stats.get("fire_7", 0) == 0

    # Fill left column (1,2,3)
    for t in (1, 2, 3):
        pos = coords_for_tree(g, 0, t)
        g.handle_mouse_click(pos, button=1)
    assert all(g.permanent_stats.get(f"fire_{t}", 0) for t in (1, 2, 3))

    # Now center can be unlocked
    g.handle_mouse_click(pos_center, button=1)
    assert g.permanent_stats.get("fire_7", 0) == 1

    # Downgrade one in left column -> center should be cleared automatically
    pos_left2 = coords_for_tree(g, 0, 2)
    g.handle_mouse_click(pos_left2, button=3)
    assert g.permanent_stats.get("fire_7", 0) == 0


def test_independent_columns_and_downgrade_behavior():
    g = Game()
    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    # Clear
    for i in range(1, 8):
        g.permanent_stats[f"storm_{i}"] = 0

    # Unlock right column tiers 4,5,6
    for t in (4, 5, 6):
        g.handle_mouse_click(coords_for_tree(g, 1, t), button=1)
    assert all(g.permanent_stats.get(f"storm_{t}", 0) for t in (4, 5, 6))

    # Downgrading tier 5 should clear 6 but keep 4
    g.handle_mouse_click(coords_for_tree(g, 1, 5), button=3)
    assert g.permanent_stats.get("storm_6", 0) == 0
    assert g.permanent_stats.get("storm_4", 0) == 1

    # Center should be unlockable since right column is full again
    g.handle_mouse_click(coords_for_tree(g, 1, 5), button=1)  # re-unlock 5
    g.handle_mouse_click(coords_for_tree(g, 1, 6), button=1)  # unlock 6
    g.handle_mouse_click(coords_for_tree(g, 1, 7), button=1)  # unlock center
    assert g.permanent_stats.get("storm_7", 0) == 1

    # Downgrade tier 4 (top of right column) and verify center cleared
    g.handle_mouse_click(coords_for_tree(g, 1, 4), button=3)
    assert g.permanent_stats.get("storm_7", 0) == 0
