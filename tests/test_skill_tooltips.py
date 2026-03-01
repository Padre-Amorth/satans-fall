#!/usr/bin/env python3
"""Tests for skill tree tooltip content and rendering safety."""

from game import Game


def test_tooltip_lines_tier_requirements():
    g = Game()
    # Ensure base cleared
    for i in range(1, 8):
        g.permanent_stats[f"fire_{i}"] = 0

    lines = g._skill_tooltip_lines("fire", 1)
    # FIRE tier 1 has a specific effect description (burn propagation on death)
    assert any("on death" in line or "chains up to 3" in line for line in lines)

    lines2 = g._skill_tooltip_lines("fire", 2)
    assert any("Burn duration ×2; burn DPS ×2" in line for line in lines2)

    # FIRE tier 3 should describe the +25% damage vs burning enemies
    lines3left = g._skill_tooltip_lines("fire", 3)
    assert any("+25% damage to burning enemies" in line for line in lines3left)

    # STORM left-column tiers (1..3) should describe their tier-specific effects
    lines_s1 = g._skill_tooltip_lines("storm", 1)
    assert any("Chain lightning +2 targets" in line for line in lines_s1)

    lines_s2 = g._skill_tooltip_lines("storm", 2)
    assert any(
        "Chain-kills trigger lightning explosion" in line
        or "lightning explosion" in line
        for line in lines_s2
    )

    lines_s3 = g._skill_tooltip_lines("storm", 3)
    assert any("Chain lightning +2 targets" in line for line in lines_s3)

    # ICE left-column tier 1 should describe area damage and slow
    lines_i1 = g._skill_tooltip_lines("ice", 1)
    assert any(
        "Projectiles deal area damage and create slowing puddles" in line
        for line in lines_i1
    )

    # ICE left-column tier 2 should describe increased area
    lines_i2 = g._skill_tooltip_lines("ice", 2)
    assert any("+50% puddle area and area damage radius" in line for line in lines_i2)

    # Right-column tiers should show the new per-slot effect text
    for tier in (4, 5, 6):
        lines_r = g._skill_tooltip_lines("fire", tier)
        assert any(line.startswith("+10% dmg, +10% crit chance") for line in lines_r)

    # STORM right-column now shows +20% fire rate per slot (crit chance instead of dmg)
    for tier in (4, 5, 6):
        lines_s = g._skill_tooltip_lines("storm", tier)
        assert any(
            line.startswith("+10% crit chance, +20% fire rate") for line in lines_s
        )

    # ICE right-column now shows +20% damage per slot (fire rate remains +10%)
    for tier in (4, 5, 6):
        lines_i = g._skill_tooltip_lines("ice", tier)
        assert any(line.startswith("+20% dmg, +10% fire rate") for line in lines_i)

    # center tier 7 upgrades should have their creative names
    fuel7 = g._skill_tooltip_lines("fire", 7)
    assert any("AR.MAGA.EDDON" in line for line in fuel7)
    assert any("Fires 4 mortar charges" in line for line in fuel7)
    # description no longer mentions delay or words; previous checks retired
    storm7 = g._skill_tooltip_lines("storm", 7)
    assert any("Voltaic Mayhem" in line for line in storm7)
    assert any("Right-click" in line or "controllable" in line for line in storm7)
    # new speed description should also be present
    assert any("speed" in line and "px" in line for line in storm7)
    ice7 = g._skill_tooltip_lines("ice", 7)
    assert any("Blizzard" in line for line in ice7)


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
    g._draw_tooltip(
        lines,
        mid_col_x,
        tooltip_y,
        __import__("pygame").font.Font(None, 18),
        anchor_center=True,
    )


def test_tooltip_no_header():
    g = Game()
    # Ensure base cleared
    for i in range(1, 8):
        g.permanent_stats[f"fire_{i}"] = 0
    lines = g._skill_tooltip_lines("fire", 1)
    # There should be no header line containing 'Tier' or the label
    assert not any("Tier" in line or "FIRE" in line for line in lines)


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
    # Center tier has no effect, just empty
