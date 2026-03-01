#!/usr/bin/env python3
"""Tests for the skill trees in Permanent Upgrades (FIRE/STORM/ICE)."""

import os
import sys


from game import Game


def test_skill_tree_unlock_and_persistence(tmp_path):
    _ = tmp_path / "perm_stats.json"

    g = Game()
    g.showing_permanent_upgrades = True
    g.showing_stage_menu = False  # ensure clicks are routed to permanent upgrades

    # Compute coordinates matching the layout in draw_permanent_upgrades
    left_x = g.width // 2 - 420
    separator_y = 320
    tree_base_x = left_x + 680
    tree_col_spacing = 120
    tree_box_w = 50
    tree_box_h = 36
    tree_v_spacing = 46
    tree_top_y = separator_y - 150

    # FIRE left column tier 1 (top)
    fire_col_x = tree_base_x + 0 * tree_col_spacing
    inner_col_offset = tree_box_w // 2 + 1
    fire_left_x = fire_col_x - inner_col_offset
    fire_t1_y = tree_top_y

    # Click to unlock FIRE tier 1 (left top)
    g.handle_mouse_click((fire_left_x, fire_t1_y + tree_box_h // 2), button=1)
    assert g.permanent_stats.get("fire_1") == 1

    # Try to unlock FIRE tier 2 (left middle) (should succeed only if tier1 unlocked)
    fire_t2_y = tree_top_y + 1 * tree_v_spacing
    g.handle_mouse_click((fire_left_x, fire_t2_y + tree_box_h // 2), button=1)
    assert g.permanent_stats.get("fire_2") == 1

    # Right click tier1 should clear tier2
    g.handle_mouse_click((fire_left_x, fire_t1_y + tree_box_h // 2), button=3)
    assert g.permanent_stats.get("fire_1") == 0
    assert g.permanent_stats.get("fire_2") == 0

    # Persistence is disabled now; a new game should forget the change
    g.permanent_stats["storm_1"] = 1
    g2 = Game()
    assert g2.permanent_stats.get("storm_1", 0) == 0
