"""Test Health Regen upgrade system.

Tests covering:
- Health Regen upgrade availability in all stages
- Health Regen applies +1 HP per 5 seconds per upgrade
- Regeneration happens at correct intervals (300 frames @ 60 FPS = 5 seconds)
- Multiple upgrades stack additively
- Regeneration capped at max_health
- Regeneration timer resets after healing
- No regeneration with 0 upgrades
- Regeneration is passive (no action required)
"""

from __future__ import annotations

import pytest

from src.game import Game


def _contains_health_regen(choices: list[dict]) -> bool:
    """Check if Health Regen upgrade is in the choices."""
    return any(c.get("id") == "health_regen" for c in choices)


def test_health_regen_upgrade_available_in_limbo():
    """Health Regen upgrade should be available in Limbo stage."""
    g = Game()
    g.selected_stage = "limbo"

    found = False
    for _ in range(60):
        choices = g.generate_upgrade_choices()
        if _contains_health_regen(choices):
            found = True
            break
    assert found, "Health Regen upgrade not found in Limbo after multiple draws"


def test_health_regen_upgrade_available_in_purgatory():
    """Health Regen upgrade should be available in Purgatory stage."""
    g = Game()
    g.selected_stage = "purgatory"

    found = False
    for _ in range(60):
        choices = g.generate_upgrade_choices()
        if _contains_health_regen(choices):
            found = True
            break
    assert found, "Health Regen upgrade not found in Purgatory after multiple draws"


def test_health_regen_upgrade_available_in_hell():
    """Health Regen upgrade should be available in Hell stage."""
    g = Game()
    g.selected_stage = "hell"

    found = False
    for _ in range(60):
        choices = g.generate_upgrade_choices()
        if _contains_health_regen(choices):
            found = True
            break
    assert found, "Health Regen upgrade not found in Hell after multiple draws"


def test_single_health_regen_upgrade():
    """First Health Regen upgrade should set regen_per_5s = 1.0."""
    g = Game()
    g.selected_stage = "limbo"

    # Initially no regen
    assert g.player.regen_per_5s == 0.0
    assert g.player.regen_timer == 0

    # Find and apply Health Regen upgrade
    regen = None
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        regen = next((c for c in choices if c.get("id") == "health_regen"), None)
        if regen:
            break

    assert regen, "Could not find Health Regen upgrade"
    g.apply_upgrade(regen)

    assert g.player.regen_per_5s == 1.0
    assert g.player.regen_timer == 0


def test_health_regen_happens_after_300_frames():
    """Health regeneration should trigger after 300 frames (5 seconds at 60 FPS)."""
    g = Game()
    g.selected_stage = "limbo"

    # Apply Health Regen upgrade
    regen = None
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        regen = next((c for c in choices if c.get("id") == "health_regen"), None)
        if regen:
            break

    g.apply_upgrade(regen)

    # Damage player
    g.player.health = 50
    initial_health = g.player.health

    # Simulate 299 frames (just before regen should happen)
    for _ in range(299):
        g.player.update(1280)

    assert g.player.health == initial_health, "Health should not regen yet at frame 299"

    # Simulate 1 more frame to reach 300
    g.player.update(1280)

    # Health should have increased by 1
    assert g.player.health == initial_health + 1


def test_health_regen_timer_resets():
    """Regen timer should reset after healing."""
    g = Game()
    g.selected_stage = "limbo"

    # Apply Health Regen upgrade
    regen = None
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        regen = next((c for c in choices if c.get("id") == "health_regen"), None)
        if regen:
            break

    g.apply_upgrade(regen)

    # Run for 300 frames to trigger first regen
    for _ in range(300):
        g.player.update(1280)

    assert g.player.health > 50

    # Timer should be reset
    assert g.player.regen_timer == 0


def test_multiple_health_regen_upgrades_stack():
    """Multiple Health Regen upgrades should stack additively."""
    g = Game()
    g.selected_stage = "limbo"

    # Apply Health Regen upgrade 3 times
    for i in range(3):
        regen = None
        for _ in range(200):
            choices = g.generate_upgrade_choices()
            regen = next((c for c in choices if c.get("id") == "health_regen"), None)
            if regen:
                break
        g.apply_upgrade(regen)

    # Should have 3.0 HP per 5 seconds
    assert g.player.regen_per_5s == 3.0

    # Damage and test
    g.player.health = 50

    # Run for 300 frames
    for _ in range(300):
        g.player.update(1280)

    # Health should have increased by 3
    assert g.player.health == pytest.approx(53.0, abs=0.1)


def test_health_regen_capped_at_max_health():
    """Health regeneration should not exceed max_health."""
    g = Game()
    g.selected_stage = "limbo"

    # Apply Health Regen upgrade
    regen = None
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        regen = next((c for c in choices if c.get("id") == "health_regen"), None)
        if regen:
            break

    g.apply_upgrade(regen)

    max_health = g.player.max_health
    g.player.health = max_health - 0.5  # Very close to max

    # Run for 300 frames
    for _ in range(300):
        g.player.update(1280)

    # Health should be capped at max_health
    assert g.player.health <= max_health


def test_no_regen_without_upgrade():
    """Player should not regenerate health without Health Regen upgrade."""
    g = Game()
    g.selected_stage = "limbo"

    # Damage player
    g.player.health = 50
    initial_health = g.player.health

    # Run for 300 frames without upgrade
    for _ in range(300):
        g.player.update(1280)

    # Health should not have changed
    assert g.player.health == initial_health


def test_health_regen_is_passive():
    """Health regeneration should happen automatically during update."""
    g = Game()
    g.selected_stage = "limbo"

    # Apply Health Regen upgrade
    regen = None
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        regen = next((c for c in choices if c.get("id") == "health_regen"), None)
        if regen:
            break

    g.apply_upgrade(regen)

    g.player.health = 50

    # Just call update without any special handling
    for _ in range(300):
        g.player.update(1280)

    # Should have healed passively
    assert g.player.health > 50
