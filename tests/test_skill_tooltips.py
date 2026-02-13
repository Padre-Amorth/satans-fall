#!/usr/bin/env python3
"""Tests for skill tree tooltip content and rendering safety."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from game import Game


def test_tooltip_lines_tier_requirements():
    g = Game()
    # Ensure base cleared
    for i in range(1, 8):
        g.permanent_stats[f"fire_{i}"] = 0

    lines = g._skill_tooltip_lines("fire", 1)
    # 'Requirement' text should no longer be present; we expect a status and an Effect placeholder
    assert any(l.startswith("Status:") for l in lines)
    assert any(l.startswith("Effect:") for l in lines)
    # FIRE tier 1 has a specific effect description (burn propagation on death)
    assert any("on death" in l or "chains up to 3" in l for l in lines)

    lines2 = g._skill_tooltip_lines("fire", 2)
    assert any(l.startswith("Status:") for l in lines2)
    assert any(l.startswith("Effect:") for l in lines2)

    # FIRE tier 3 should describe the +25% damage vs burning enemies
    lines3left = g._skill_tooltip_lines("fire", 3)
    assert any(l.startswith("Effect: +25% damage to burning enemies") for l in lines3left)

    # STORM left-column tiers (1..3) should describe chain-target bonus
    for tier in (1, 2, 3):
        lines_sl = g._skill_tooltip_lines("storm", tier)
        assert any("Chain lightning +1 target" in l for l in lines_sl)

    # Center when no full column
    lines3 = g._skill_tooltip_lines("fire", 7)
    assert any(l.startswith("Status:") for l in lines3)
    assert any(l.startswith("Effect:") for l in lines3)

    # Fill left column and ensure center still only shows Effect placeholder (no unlock hint)
    for t in (1, 2, 3):
        g.permanent_stats[f"fire_{t}"] = 1
    lines4 = g._skill_tooltip_lines("fire", 7)
    assert any(l.startswith("Status:") for l in lines4)
    assert any(l.startswith("Effect:") for l in lines4)

    # Right-column tiers should show the new per-slot effect text
    for tier in (4, 5, 6):
        lines_r = g._skill_tooltip_lines("fire", tier)
        assert any(l.startswith("Effect: +10% dmg, +10% fire rate") for l in lines_r)

    # STORM right-column now shows +20% fire rate per slot (damage still +10%)
    for tier in (4, 5, 6):
        lines_s = g._skill_tooltip_lines("storm", tier)
        assert any(l.startswith("Effect: +10% dmg, +20% fire rate") for l in lines_s)

    # ICE right-column now shows +20% damage per slot (fire rate remains +10%)
    for tier in (4, 5, 6):
        lines_i = g._skill_tooltip_lines("ice", tier)
        assert any(l.startswith("Effect: +20% dmg, +10% fire rate") for l in lines_i)


def test_draw_tooltip_does_not_crash_when_hovering_over_tree():
    g = Game()
    # Position mouse over left top fire
    coords = (g.width // 2 - 420 + 680 - (50 // 2), 170)
    g.mouse_x, g.mouse_y = coords
    # Call draw method; should not raise
    g.showing_permanent_upgrades = True
    g.showing_stage_menu = False
    g.draw_permanent_upgrades()  # should not raise


def test_draw_fixed_tooltip_position():
    g = Game()
    # Hover over the left top fire and check that _draw_tooltip can be called with anchor_center
    g.showing_permanent_upgrades = True
    g.showing_stage_menu = False
    lines = g._skill_tooltip_lines("fire", 1)
    # call drawing with anchor_center True at column center
    left_x = g.width // 2 - 420
    tree_base_x = left_x + 680
    mid_col_x = tree_base_x
    tooltip_y = (g.height // 2) + 200
    # Should not raise
    g._draw_tooltip(lines, mid_col_x, tooltip_y, __import__("pygame").font.Font(None, 18), anchor_center=True)


def test_tooltip_no_header():
    g = Game()
    # Ensure base cleared
    for i in range(1, 8):
        g.permanent_stats[f"fire_{i}"] = 0
    lines = g._skill_tooltip_lines("fire", 1)
    # There should be no header line containing 'Tier' or the label
    assert not any("Tier" in l or "FIRE" in l for l in lines)


def test_center_tooltip_shows_under_tree():
    g = Game()
    g.showing_permanent_upgrades = True
    g.showing_stage_menu = False
    # Ensure center tier coordinates
    left_x = g.width // 2 - 420
    tree_base_x = left_x + 680
    tree_col_x = tree_base_x + 0 * 120
    tree_top_y = 320 - 150
    center_x = tree_col_x
    center_y = tree_top_y + 3 * 46 + 36 // 2
    # Move mouse over center box
    g.mouse_x, g.mouse_y = (center_x, center_y)
    # Call draw; should not raise and should be able to build tooltip lines
    g.draw_permanent_upgrades()
    lines = g._skill_tooltip_lines("fire", 7)
    assert any(l.startswith("Status:") for l in lines)
    assert any(l.startswith("Effect:") for l in lines)