#!/usr/bin/env python3
"""Test right-click downgrade functionality for permanent stats, blasphemies, and skill trees."""

import pytest
from src.game import Game


def test_right_click_downgrade_power_stat():
    """Test that right-clicking on POWER stat downgrades it."""
    g = Game()
    # Don't load from profile file - set active_profile_slot to None temporarily
    original_slot = g.active_profile_slot
    g.active_profile_slot = None

    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    # Set up: power at level 3, 0 meta_points to start
    g.permanent_stats.clear()
    g.permanent_stats["power"] = 3
    g.global_progress["meta_points"] = 0
    g.apply_permanent_stats()

    # Calculate correct position for POWER stat (y=140)
    left_x = g.width // 2 - 420
    power_pos = (left_x + 5, 140 + 5)

    # Right-click to downgrade
    g.handle_mouse_click(power_pos, button=3)

    # Verify downgrade happened
    assert g.permanent_stats["power"] == 2, f"Expected power=2, got {g.permanent_stats['power']}"
    assert g.global_progress["meta_points"] == 1, "Meta point should be refunded"


def test_right_click_downgrade_blasphemy_1():
    """Test that right-clicking on Blasphemy 1 downgrades it."""
    g = Game()
    g.active_profile_slot = None  # Don't load from profile file

    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    # Set up: blasphemy_1 at level 2
    g.permanent_stats.clear()
    g.permanent_stats["blasphemy_1"] = 2
    g.global_progress["meta_points"] = 0
    g.apply_permanent_stats()

    # Blasphemy grid position calculation (top row, first box)
    left_x = g.width // 2 - 420
    box_spacing = 100
    start_x = left_x + box_spacing // 2 - 40
    separator_y = 320
    box_y1 = separator_y + 60
    box_x = start_x  # First column

    blasphemy_pos = (box_x, box_y1 + 5)

    # Right-click to downgrade
    g.handle_mouse_click(blasphemy_pos, button=3)

    # Verify downgrade happened
    assert g.permanent_stats["blasphemy_1"] == 1, f"Expected blasphemy_1=1, got {g.permanent_stats['blasphemy_1']}"


def test_right_click_downgrade_skill_tree():
    """Test that right-clicking on a skill tree tier downgrades it."""
    g = Game()
    g.active_profile_slot = None  # Don't load from profile file

    g.showing_stage_menu = False
    g.showing_permanent_upgrades = True

    # Set up: fire_1, fire_2, fire_3 all unlocked (left column of fire tree)
    g.permanent_stats.clear()
    g.permanent_stats["fire_1"] = 1
    g.permanent_stats["fire_2"] = 1
    g.permanent_stats["fire_3"] = 1
    g.global_progress["meta_points"] = 0
    g.apply_permanent_stats()

    # Skill tree position calculation (fire tree, first row, left column)
    left_x = g.width // 2 - 420
    tree_base_x = left_x + 680
    tree_top_y = 320 - 150
    tree_box_w = 50
    tree_v_spacing = 46

    # First column (left), first row (y=0)
    col_x = tree_base_x  # Fire tree
    inner_col_offset = tree_box_w // 2 + 1
    left_col_x = col_x - inner_col_offset
    y = tree_top_y

    fire_1_pos = (left_col_x - tree_box_w // 2 + 5, y + 5)

    # Right-click to downgrade fire_1 (which should also clear fire_2 and fire_3)
    g.handle_mouse_click(fire_1_pos, button=3)

    # Verify downgrade cascade happened
    assert g.permanent_stats["fire_1"] == 0, f"Expected fire_1=0, got {g.permanent_stats['fire_1']}"
    assert g.permanent_stats["fire_2"] == 0, f"Expected fire_2=0, got {g.permanent_stats['fire_2']}"
    assert g.permanent_stats["fire_3"] == 0, f"Expected fire_3=0, got {g.permanent_stats['fire_3']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
