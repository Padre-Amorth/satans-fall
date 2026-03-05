"""Test availability and application of all per-run upgrades.

Comprehensive tests ensuring:
- All upgrades are available in appropriate stages
- Upgrade names match expected format
- Upgrade descriptions exist and are non-empty
- All upgrades can be applied without errors
- Upgrade effects are applied to the correct targets (game, player, etc.)
- Multiple upgrades can be applied in sequence
- Upgrade availability respects stage restrictions
"""

from __future__ import annotations

from src.game import Game

EXPECTED_UPGRADES = {
    "damage": {"name": "Damage +10%", "all_stages": True},
    "fire_rate": {"name": "Fire Rate +10%", "all_stages": True},
    "max_health": {"name": "Max Health +20", "all_stages": True},
    "projectile_size": {
        "name": "Projectile Size +10%",
        "all_stages": False,
        "only": ["hell"],
    },
    "movement_speed": {"name": "Movement Speed +5%", "all_stages": True},
    "health_regen": {"name": "Health Regen +1 HP/5s", "all_stages": True},
    "xp": {"name": "XP +10%", "all_stages": True},
    "tower_fire_rate": {
        "name": "Tower Fire Rate +10%",
        "all_stages": False,
        "only": ["purgatory", "hell"],
    },
    "armor": {"name": "Armor +5%", "all_stages": True},
    "shield": {"name": "SHIELD", "all_stages": False, "exclude": ["prologo"]},
    "kill_explosion": {
        "name": "BOOM!",
        "all_stages": False,
        "only": ["purgatory", "hell"],
    },
}


def test_all_upgrades_have_required_fields():
    """Verify all expected upgrades exist with required fields."""
    # Use Purgatory which has access to most upgrades including tower_fire_rate
    g = Game()
    g.selected_stage = "purgatory"

    found_upgrades = {}
    for _ in range(500):
        choices = g.generate_upgrade_choices()
        for choice in choices:
            upgrade_id = choice.get("id")
            if upgrade_id and upgrade_id not in found_upgrades:
                found_upgrades[upgrade_id] = choice

    # Check all expected upgrades are present (tower_fire_rate will appear in purgatory)
    for upgrade_id, expected in EXPECTED_UPGRADES.items():
        # Skip stage-specific checks - we're just verifying structure
        if upgrade_id in found_upgrades:
            upgrade = found_upgrades[upgrade_id]
            assert "name" in upgrade, f"Upgrade '{upgrade_id}' missing 'name'"
            assert (
                "description" in upgrade
            ), f"Upgrade '{upgrade_id}' missing 'description'"
            assert "apply" in upgrade, f"Upgrade '{upgrade_id}' missing 'apply'"
            assert upgrade.get("name") == expected["name"], (
                f"Upgrade '{upgrade_id}' name mismatch: "
                f"expected '{expected['name']}', got '{upgrade.get('name')}'"
            )

    # Verify we found most upgrades (at least 10 out of 11)
    assert len(found_upgrades) >= 10, (
        f"Expected to find at least 10 upgrades, found {len(found_upgrades)}: "
        f"{list(found_upgrades.keys())}"
    )


def test_damage_upgrade_in_all_stages():
    """Damage upgrade should be available in all stages."""
    for stage in ["prologo", "limbo", "purgatory", "hell"]:
        g = Game()
        g.selected_stage = stage

        found = False
        for _ in range(60):
            choices = g.generate_upgrade_choices()
            if any(c.get("id") == "damage" for c in choices):
                found = True
                break

        assert found, f"Damage upgrade not found in stage {stage}"


def test_fire_rate_upgrade_in_all_stages():
    """Fire Rate upgrade should be available in all stages."""
    for stage in ["prologo", "limbo", "purgatory", "hell"]:
        g = Game()
        g.selected_stage = stage

        found = False
        for _ in range(60):
            choices = g.generate_upgrade_choices()
            if any(c.get("id") == "fire_rate" for c in choices):
                found = True
                break

        assert found, f"Fire Rate upgrade not found in stage {stage}"


def test_max_health_upgrade_in_all_stages():
    """Max Health upgrade should be available in all stages."""
    for stage in ["prologo", "limbo", "purgatory", "hell"]:
        g = Game()
        g.selected_stage = stage

        found = False
        for _ in range(60):
            choices = g.generate_upgrade_choices()
            if any(c.get("id") == "max_health" for c in choices):
                found = True
                break

        assert found, f"Max Health upgrade not found in stage {stage}"


def test_movement_speed_upgrade_in_all_stages():
    """Movement Speed upgrade should be available in all stages."""
    for stage in ["prologo", "limbo", "purgatory", "hell"]:
        g = Game()
        g.selected_stage = stage

        found = False
        for _ in range(60):
            choices = g.generate_upgrade_choices()
            if any(c.get("id") == "movement_speed" for c in choices):
                found = True
                break

        assert found, f"Movement Speed upgrade not found in stage {stage}"


def test_armor_upgrade_in_all_stages():
    """Armor upgrade should be available in all stages."""
    for stage in ["prologo", "limbo", "purgatory", "hell"]:
        g = Game()
        g.selected_stage = stage

        found = False
        for _ in range(60):
            choices = g.generate_upgrade_choices()
            if any(c.get("id") == "armor" for c in choices):
                found = True
                break

        assert found, f"Armor upgrade not found in stage {stage}"


def test_projectile_size_excluded_in_prologo():
    """Projectile Size upgrade should NOT be in Prologo."""
    g = Game()
    g.selected_stage = "prologo"

    for _ in range(20):
        choices = g.generate_upgrade_choices()
        assert not any(c.get("id") == "projectile_size" for c in choices)


def test_tower_fire_rate_only_in_purgatory_hell():
    """Tower Fire Rate upgrade should only be in Purgatory and Hell."""
    # Should NOT be in Prologo and Limbo
    for stage in ["prologo", "limbo"]:
        g = Game()
        g.selected_stage = stage

        for _ in range(20):
            choices = g.generate_upgrade_choices()
            assert not any(
                c.get("id") == "tower_fire_rate" for c in choices
            ), f"Tower Fire Rate should not be in {stage}"

    # Should be in Purgatory and Hell
    for stage in ["purgatory", "hell"]:
        g = Game()
        g.selected_stage = stage

        found = False
        for _ in range(60):
            choices = g.generate_upgrade_choices()
            if any(c.get("id") == "tower_fire_rate" for c in choices):
                found = True
                break

        assert found, f"Tower Fire Rate not found in {stage}"


def test_multiple_upgrades_apply_sequentially():
    """Multiple upgrades should apply without error in sequence."""
    g = Game()
    g.selected_stage = "limbo"

    applied = []
    for i in range(10):
        for _ in range(200):
            choices = g.generate_upgrade_choices()
            if choices:
                choice = choices[0]  # Take first available
                g.apply_upgrade(choice)
                applied.append(choice.get("id"))
                break

    # Should have applied 10 upgrades
    assert len(applied) == 10, f"Expected 10 upgrades applied, got {len(applied)}"


def test_upgrade_apply_callback_executes():
    """Upgrade apply callbacks should execute without errors."""
    g = Game()
    g.selected_stage = "limbo"

    for _ in range(100):
        choices = g.generate_upgrade_choices()
        for choice in choices:
            # Record state before
            if choice.get("id") == "damage":
                before = g.player_damage
                g.apply_upgrade(choice)
                after = g.player_damage
                assert after > before, "Damage upgrade should increase player_damage"
                return

    assert False, "Could not find and apply damage upgrade"


def test_shield_upgrade_max_level_filtering():
    """Shield upgrade should be filtered out when at level 5."""
    g = Game()
    g.selected_stage = "limbo"

    # Apply shield 5 times
    for _ in range(5):
        for _ in range(200):
            choices = g.generate_upgrade_choices()
            shield = next((c for c in choices if c.get("id") == "shield"), None)
            if shield:
                g.apply_upgrade(shield)
                break

    assert g.player.shield_upgrade_level == 5

    # Shield should not appear anymore
    for _ in range(20):
        choices = g.generate_upgrade_choices()
        assert not any(
            c.get("id") == "shield" for c in choices
        ), "Shield should be filtered at max level 5"


def test_all_upgrades_have_non_empty_descriptions():
    """All upgrades should have non-empty descriptions."""
    g = Game()
    g.selected_stage = "purgatory"

    descriptions_seen = {}
    for _ in range(300):
        choices = g.generate_upgrade_choices()
        for choice in choices:
            upgrade_id = choice.get("id")
            if upgrade_id not in descriptions_seen:
                desc = choice.get("description", "")
                descriptions_seen[upgrade_id] = desc
                assert (
                    desc and len(desc) > 0
                ), f"Upgrade '{upgrade_id}' has empty or missing description"

    # Should have seen most upgrades (Purgatory has all 11)
    assert (
        len(descriptions_seen) >= 10
    ), f"Expected to see at least 10 different upgrades, saw {len(descriptions_seen)}"
