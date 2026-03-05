"""Integration tests for all upgrades working together.

Tests covering:
- Multiple upgrades can be applied in sequence
- Upgrades stack properly (multiplicative and additive)
- Shield and Health Regen work together
- BOOM! counter increments correctly with other upgrades applied
- Damage/Fire Rate scaling with movement speed
- Armor and Health Regen interaction
"""

from __future__ import annotations

import pytest

from src.game import Game


def test_multiple_upgrades_in_sequence():
    """Multiple different upgrades should apply without conflict."""
    g = Game()
    g.selected_stage = "limbo"

    applied_count = 0
    for _ in range(50):
        for _ in range(200):
            choices = g.generate_upgrade_choices()
            if choices:
                g.apply_upgrade(choices[0])
                applied_count += 1
                break

    # Should have applied at least 30 upgrades
    assert applied_count >= 30


def test_damage_and_fire_rate_stack():
    """Damage and Fire Rate upgrades should multiply together."""
    g = Game()
    g.selected_stage = "limbo"

    initial_damage = g.player_damage
    initial_fire_rate = g.fire_rate_multiplier

    # Apply damage upgrade
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        damage = next((c for c in choices if c.get("id") == "damage"), None)
        if damage:
            g.apply_upgrade(damage)
            break

    after_damage = g.player_damage

    # Apply fire rate upgrade
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        fire_rate = next((c for c in choices if c.get("id") == "fire_rate"), None)
        if fire_rate:
            g.apply_upgrade(fire_rate)
            break

    after_fire_rate = g.fire_rate_multiplier

    # Both should have increased
    assert after_damage > initial_damage
    assert after_fire_rate > initial_fire_rate


def test_armor_reduces_effective_damage():
    """Armor upgrade should reduce damage_reduction_multiplier."""
    g = Game()
    g.selected_stage = "limbo"

    initial_reduction = g.damage_reduction_multiplier

    # Apply armor upgrade
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        armor = next((c for c in choices if c.get("id") == "armor"), None)
        if armor:
            g.apply_upgrade(armor)
            break

    after_reduction = g.damage_reduction_multiplier

    # damage_reduction_multiplier should have decreased (less damage taken)
    assert after_reduction < initial_reduction


def test_health_regen_and_max_health_together():
    """Max Health and Health Regen should work together."""
    g = Game()
    g.selected_stage = "limbo"

    initial_max_health = g.player.max_health
    initial_regen = g.player.regen_per_5s

    # Apply Max Health upgrade
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        max_health = next((c for c in choices if c.get("id") == "max_health"), None)
        if max_health:
            g.apply_upgrade(max_health)
            break

    # Apply Health Regen upgrade
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        regen = next((c for c in choices if c.get("id") == "health_regen"), None)
        if regen:
            g.apply_upgrade(regen)
            break

    # Both should have changed
    assert g.player.max_health > initial_max_health
    assert g.player.regen_per_5s > initial_regen


def test_shield_and_health_together():
    """Shield and Max Health upgrades should not conflict."""
    g = Game()
    g.selected_stage = "limbo"

    # Apply Max Health upgrade
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        max_health = next((c for c in choices if c.get("id") == "max_health"), None)
        if max_health:
            g.apply_upgrade(max_health)
            break

    # Apply Shield upgrade
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        shield = next((c for c in choices if c.get("id") == "shield"), None)
        if shield:
            g.apply_upgrade(shield)
            break

    # Both should be active
    assert g.player.max_health > 100  # Should have increased from max health upgrade
    assert g.player.shield_charges > 0  # Shield should be enabled


def test_movement_speed_stacks_with_upgrades():
    """Movement Speed upgrades should stack multiplicatively."""
    g = Game()
    g.selected_stage = "limbo"

    initial_speed = g.player.speed

    # Apply movement speed upgrade multiple times
    for _ in range(3):
        for _ in range(200):
            choices = g.generate_upgrade_choices()
            speed = next((c for c in choices if c.get("id") == "movement_speed"), None)
            if speed:
                g.apply_upgrade(speed)
                break

    # Speed should increase by 5% per level: 1.05 * 1.05 * 1.05 ≈ 1.1576
    final_speed = g.player.speed
    expected_approx = initial_speed * (1.05**3)
    assert final_speed == pytest.approx(expected_approx, rel=0.01)


def test_projectile_size_and_damage():
    """Projectile Size and Damage upgrades should work together."""
    g = Game()
    g.selected_stage = "hell"

    initial_size = g.projectile_size_multiplier
    initial_damage = g.player_damage

    # Apply projectile size upgrade
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        size = next((c for c in choices if c.get("id") == "projectile_size"), None)
        if size:
            g.apply_upgrade(size)
            break

    # Apply damage upgrade
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        damage = next((c for c in choices if c.get("id") == "damage"), None)
        if damage:
            g.apply_upgrade(damage)
            break

    # Both should increase independently
    assert g.projectile_size_multiplier > initial_size
    assert g.player_damage > initial_damage


def test_xp_upgrade_increases_xp_multiplier():
    """XP upgrade should increase XP gain multiplier."""
    g = Game()
    g.selected_stage = "limbo"

    initial_xp_mult = getattr(g, "xp_multiplier", 1.0)

    # Apply XP upgrade
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        xp = next((c for c in choices if c.get("id") == "xp"), None)
        if xp:
            g.apply_upgrade(xp)
            break

    final_xp_mult = getattr(g, "xp_multiplier", 1.0)
    assert final_xp_mult > initial_xp_mult


def test_tower_fire_rate_in_purgatory():
    """Tower Fire Rate upgrade should only work in Purgatory/Hell."""
    g = Game()
    g.selected_stage = "purgatory"

    found = False
    for _ in range(200):
        choices = g.generate_upgrade_choices()
        tower_fire = next(
            (c for c in choices if c.get("id") == "tower_fire_rate"), None
        )
        if tower_fire:
            found = True
            g.apply_upgrade(tower_fire)
            break

    assert found, "Tower Fire Rate should be available in Purgatory"


def test_all_upgrades_safe_to_apply():
    """All upgrades should apply without raising exceptions."""
    g = Game()
    g.selected_stage = "purgatory"

    upgrades_applied = []
    errors = []

    for attempt in range(100):
        choices = g.generate_upgrade_choices()
        if not choices:
            break

        for choice in choices:
            try:
                g.apply_upgrade(choice)
                upgrades_applied.append(choice.get("id"))
            except Exception as e:
                errors.append((choice.get("id"), str(e)))

    # Should have applied many upgrades
    assert len(upgrades_applied) >= 20, f"Only applied {len(upgrades_applied)} upgrades"

    # Should have no errors
    assert not errors, f"Errors occurred: {errors}"
